(vl-load-com)

(defun pg:read-file (path / file line lines)
  (setq file (open path "r"))
  (if file
    (progn
      (setq lines '())
      (while (setq line (read-line file))
        (setq lines (cons line lines))
      )
      (close file)
      (apply 'strcat (reverse lines))
    )
    nil
  )
)

(defun pg:skip-ws (text idx / ch len)
  (setq len (strlen text))
  (while
    (and (<= idx len)
         (setq ch (substr text idx 1))
         (member ch '(" " "\t" "\r" "\n"))
    )
    (setq idx (1+ idx))
  )
  idx
)

(defun pg:parse-string (text idx / done len ch next result)
  (setq len (strlen text))
  (setq idx (1+ idx))
  (setq result "")
  (setq done nil)
  (while (and (<= idx len) (not done))
    (setq ch (substr text idx 1))
    (cond
      ((= ch "\"")
        (setq idx (1+ idx))
        (setq done T)
      )
      ((= ch "\\")
        (setq idx (1+ idx))
        (if (> idx len)
          (setq done T)
          (progn
            (setq next (substr text idx 1))
            (cond
              ((= next "\"") (setq result (strcat result "\"")))
              ((= next "\\") (setq result (strcat result "\\")))
              ((= next "/") (setq result (strcat result "/")))
              ((= next "b") (setq result (strcat result "\b")))
              ((= next "f") (setq result (strcat result "\f")))
              ((= next "n") (setq result (strcat result "\n")))
              ((= next "r") (setq result (strcat result "\r")))
              ((= next "t") (setq result (strcat result "\t")))
              (T (setq result (strcat result next)))
            )
            (setq idx (1+ idx))
          )
        )
      )
      (T
        (setq result (strcat result ch))
        (setq idx (1+ idx))
      )
    )
  )
  (list result idx)
)

(defun pg:number-char-p (ch)
  (or
    (wcmatch ch "[0-9]")
    (member ch '("+" "-" "." "e" "E"))
  )
)

(defun pg:parse-number (text idx / len start ch token)
  (setq len (strlen text))
  (setq start idx)
  (while
    (and (<= idx len)
         (setq ch (substr text idx 1))
         (pg:number-char-p ch)
    )
    (setq idx (1+ idx))
  )
  (setq token (substr text start (- idx start)))
  (list (atof token) idx)
)

(defun pg:parse-literal (text idx literal value / end)
  (setq end (+ idx (strlen literal) -1))
  (if (= (substr text idx (strlen literal)) literal)
    (list value (1+ end))
    (list nil idx)
  )
)

(defun pg:parse-array (text idx / len items parsed value)
  (setq len (strlen text))
  (setq idx (1+ idx))
  (setq items '())
  (setq idx (pg:skip-ws text idx))
  (if (= (substr text idx 1) "]")
    (list (reverse items) (1+ idx))
    (progn
      (while (<= idx len)
        (setq parsed (pg:parse-value text idx))
        (setq value (car parsed))
        (setq idx (pg:skip-ws text (cadr parsed)))
        (setq items (cons value items))
        (cond
          ((= (substr text idx 1) ",")
            (setq idx (pg:skip-ws text (1+ idx)))
          )
          ((= (substr text idx 1) "]")
            (setq idx (1+ idx))
            (setq len 0)
          )
          (T
            (setq len 0)
          )
        )
      )
      (list (reverse items) idx)
    )
  )
)

(defun pg:parse-object (text idx / len pairs key parsed value)
  (setq len (strlen text))
  (setq idx (1+ idx))
  (setq pairs '())
  (setq idx (pg:skip-ws text idx))
  (if (= (substr text idx 1) "}")
    (list (reverse pairs) (1+ idx))
    (progn
      (while (<= idx len)
        (setq parsed (pg:parse-string text idx))
        (setq key (car parsed))
        (setq idx (pg:skip-ws text (cadr parsed)))
        (if (= (substr text idx 1) ":")
          (setq idx (pg:skip-ws text (1+ idx)))
        )
        (setq parsed (pg:parse-value text idx))
        (setq value (car parsed))
        (setq idx (pg:skip-ws text (cadr parsed)))
        (setq pairs (cons (cons key value) pairs))
        (cond
          ((= (substr text idx 1) ",")
            (setq idx (pg:skip-ws text (1+ idx)))
          )
          ((= (substr text idx 1) "}")
            (setq idx (1+ idx))
            (setq len 0)
          )
          (T
            (setq len 0)
          )
        )
      )
      (list (reverse pairs) idx)
    )
  )
)

(defun pg:parse-value (text idx / ch)
  (setq idx (pg:skip-ws text idx))
  (setq ch (substr text idx 1))
  (cond
    ((= ch "{") (pg:parse-object text idx))
    ((= ch "[") (pg:parse-array text idx))
    ((= ch "\"") (pg:parse-string text idx))
    ((or (= ch "-") (wcmatch ch "[0-9]")) (pg:parse-number text idx))
    ((= (substr text idx 4) "true") (pg:parse-literal text idx "true" T))
    ((= (substr text idx 5) "false") (pg:parse-literal text idx "false" nil))
    ((= (substr text idx 4) "null") (pg:parse-literal text idx "null" nil))
    (T (list nil idx))
  )
)

(defun pg:json-parse (text / parsed)
  (setq parsed (pg:parse-value text 1))
  (car parsed)
)

(defun pg:json-get (obj key)
  (cdr (assoc key obj))
)

(defun pg:number (value fallback)
  (if (numberp value) value fallback)
)

(defun pg:string (value fallback)
  (if (= (type value) 'STR) value fallback)
)

(defun pg:debug (message)
  (prompt (strcat "\n[GEN] " message))
)

(defun pg:get-active-space ( / doc)
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (if (= (getvar "CVPORT") 1)
    (vla-get-PaperSpace doc)
    (vla-get-ModelSpace doc)
  )
)

(defun pg:abs (value)
  (if (< value 0.0)
    (- value)
    value
  )
)

(defun pg:make-point (x y)
  (list x y 0.0)
)

(defun pg:ensure-layer (layer color /)
  (if (not (tblsearch "LAYER" layer))
    (entmakex
      (list
        '(0 . "LAYER")
        '(100 . "AcDbSymbolTableRecord")
        '(100 . "AcDbLayerTableRecord")
        (cons 2 layer)
        '(70 . 0)
        (cons 62 color)
        '(6 . "Continuous")
      )
    )
  )
  layer
)

(defun pg:add-line (x1 y1 x2 y2 layer / entity)
  (pg:ensure-layer layer 7)
  (setq entity
    (entmakex
      (list
        '(0 . "LINE")
        '(100 . "AcDbEntity")
        (cons 8 layer)
        '(100 . "AcDbLine")
        (cons 10 (pg:make-point x1 y1))
        (cons 11 (pg:make-point x2 y2))
      )
    )
  )
  entity
)

(defun pg:add-closed-polyline (points layer / data entity)
  (pg:ensure-layer layer 7)
  (setq data
    (list
      '(0 . "LWPOLYLINE")
      '(100 . "AcDbEntity")
      (cons 8 layer)
      '(100 . "AcDbPolyline")
      (cons 90 (length points))
      '(70 . 1)
    )
  )
  (foreach pt points
    (setq data (append data (list (cons 10 (list (car pt) (cadr pt))))))
  )
  (setq entity (entmakex data))
  entity
)

(defun pg:wall-layer (wall / wallType)
  (setq wallType (pg:string (pg:json-get wall "wall_type") "full_height"))
  (if (= wallType "partial_height")
    "A-N-WALL LOW"
    "A-N-WALL"
  )
)

(defun pg:wall-rect-points (wall / x1 y1 x2 y2 minx maxx miny maxy thickness half)
  (setq x1 (pg:number (pg:json-get wall "x1") 0.0))
  (setq y1 (pg:number (pg:json-get wall "y1") 0.0))
  (setq x2 (pg:number (pg:json-get wall "x2") 0.0))
  (setq y2 (pg:number (pg:json-get wall "y2") 0.0))
  (setq thickness (pg:number (pg:json-get wall "thickness") 4.875))
  (setq half (/ thickness 2.0))
  (setq minx (min x1 x2))
  (setq maxx (max x1 x2))
  (setq miny (min y1 y2))
  (setq maxy (max y1 y2))
  (cond
    ((< (pg:abs (- x1 x2)) 0.0001)
      (list
        (list (- x1 half) miny)
        (list (+ x1 half) miny)
        (list (+ x1 half) maxy)
        (list (- x1 half) maxy)
      )
    )
    ((< (pg:abs (- y1 y2)) 0.0001)
      (list
        (list minx (- y1 half))
        (list maxx (- y1 half))
        (list maxx (+ y1 half))
        (list minx (+ y1 half))
      )
    )
    (T nil)
  )
)

(defun pg:draw-wall (wall / layer points x1 y1 x2 y2)
  (setq layer (pg:wall-layer wall))
  (setq points (pg:wall-rect-points wall))
  (if points
    (pg:add-closed-polyline points layer)
    (progn
      (setq x1 (pg:number (pg:json-get wall "x1") 0.0))
      (setq y1 (pg:number (pg:json-get wall "y1") 0.0))
      (setq x2 (pg:number (pg:json-get wall "x2") 0.0))
      (setq y2 (pg:number (pg:json-get wall "y2") 0.0))
      (pg:add-line x1 y1 x2 y2 layer)
    )
  )
)

(defun pg:draw-door (door / x1 y1 x2 y2)
  (setq x1 (pg:number (pg:json-get door "x1") 0.0))
  (setq y1 (pg:number (pg:json-get door "y1") 0.0))
  (setq x2 (pg:number (pg:json-get door "x2") 0.0))
  (setq y2 (pg:number (pg:json-get door "y2") 0.0))
  (pg:add-line x1 y1 x2 y2 "A-N-DOOR")
)

(defun pg:com-array->list (value / unwrapped)
  (setq unwrapped (vl-catch-all-apply 'vlax-variant-value (list value)))
  (if (vl-catch-all-error-p unwrapped)
    (vlax-safearray->list value)
    (vlax-safearray->list unwrapped)
  )
)

(defun pg:get-bounding-box-points (obj / minPt maxPt)
  (vla-GetBoundingBox obj 'minPt 'maxPt)
  (list
    (pg:com-array->list minPt)
    (pg:com-array->list maxPt)
  )
)

(defun pg:move-object (obj dx dy)
  (if (or (> (pg:abs dx) 0.0001) (> (pg:abs dy) 0.0001))
    (vla-Move obj (vlax-3d-point '(0.0 0.0 0.0)) (vlax-3d-point (list dx dy 0.0)))
  )
  obj
)

(defun pg:rotate-offset (x y angle / radians cosA sinA)
  (setq radians (* pi (/ angle 180.0)))
  (setq cosA (cos radians))
  (setq sinA (sin radians))
  (list
    (- (* x cosA) (* y sinA))
    (+ (* x sinA) (* y cosA))
  )
)

(defun pg:align-inserted-block (insertObj item / mode machine bbox minPt maxPt targetX targetY targetW targetD targetCx targetCy actualCx actualCy dx dy offset offsetX offsetY rotatedOffset rot)
  (if insertObj
    (progn
      (setq mode (pg:string (pg:json-get item "alignment_mode") "bbox_center"))
      (setq machine (pg:json-get item "machine"))
      (if (and (= mode "bbox_center") (listp machine))
        (progn
          (setq bbox (pg:get-bounding-box-points insertObj))
          (setq minPt (car bbox))
          (setq maxPt (cadr bbox))
          (setq targetX (pg:number (pg:json-get machine "x") 0.0))
          (setq targetY (pg:number (pg:json-get machine "y") 0.0))
          (setq targetW (pg:number (pg:json-get machine "w") 0.0))
          (setq targetD (pg:number (pg:json-get machine "d") 0.0))
          (setq targetCx (+ targetX (/ targetW 2.0)))
          (setq targetCy (+ targetY (/ targetD 2.0)))
          (setq actualCx (/ (+ (car minPt) (car maxPt)) 2.0))
          (setq actualCy (/ (+ (cadr minPt) (cadr maxPt)) 2.0))
          (setq dx (- targetCx actualCx))
          (setq dy (- targetCy actualCy))
          (pg:move-object insertObj dx dy)
        )
      )
      (setq offset (pg:json-get item "cad_offset"))
      (setq offsetX (pg:number (pg:json-get offset "x") 0.0))
      (setq offsetY (pg:number (pg:json-get offset "y") 0.0))
      (if (or (> (pg:abs offsetX) 0.0001) (> (pg:abs offsetY) 0.0001))
        (progn
          (setq rot (pg:number (pg:json-get item "rotation") 0.0))
          (setq rotatedOffset (pg:rotate-offset offsetX offsetY rot))
          (pg:move-object insertObj (car rotatedOffset) (cadr rotatedOffset))
        )
      )
    )
  )
  insertObj
)

(defun pg:insert-placement (item / blockName point x y z sx sy sz rot itemType space insertObj)
  (setq itemType (pg:string (pg:json-get item "type") "UNKNOWN"))
  (setq blockName (pg:string (pg:json-get item "block_name") ""))
  (setq point (pg:json-get item "insertion_point"))
  (setq x (pg:number (pg:json-get point "x") 0.0))
  (setq y (pg:number (pg:json-get point "y") 0.0))
  (setq z (pg:number (pg:json-get point "z") 0.0))
  (setq rot (pg:number (pg:json-get item "rotation") 0.0))
  (setq sx (pg:json-get item "scale"))
  (setq sy sx)
  (setq sz sx)

  (cond
    ((= blockName "")
      (prompt (strcat "\nSkipping " itemType ": no block_name in JSON."))
      nil
    )
    ((not (tblsearch "BLOCK" blockName))
      (prompt (strcat "\nSkipping " itemType ": block not found in drawing: " blockName))
      nil
    )
    (T
      (setq space (pg:get-active-space))
      (setq insertObj
        (vla-InsertBlock
          space
          (vlax-3d-point (list x y z))
          blockName
          (pg:number (pg:json-get sx "x") 1.0)
          (pg:number (pg:json-get sy "y") 1.0)
          (pg:number (pg:json-get sz "z") 1.0)
          (* pi (/ rot 180.0))
        )
      )
      (if insertObj
        (prompt
          (strcat
            "\nPlaced "
            itemType
            " using "
            blockName
            " at ("
            (rtos x 2 2)
            ", "
            (rtos y 2 2)
            ")."
          )
        )
        (prompt (strcat "\nFailed to insert " itemType " using " blockName "."))
      )
      insertObj
    )
  )
)

(defun c:gen ( / path text data meta format placements placementsPair walls wallsPair doors doorsPair placedCount skippedCount wallCount doorCount)
  (setq path (getfiled "Select Planetgen layout JSON" (strcat (getenv "USERPROFILE") "\\Downloads\\") "json" 16))

  (if (or (null path) (= path ""))
    (prompt "\nNo JSON file selected.")
    (progn
      (pg:debug (strcat "Reading JSON from: " path))
      (setq text (pg:read-file path))
      (if (or (null text) (= text ""))
        (prompt "\nUnable to read JSON file.")
        (progn
          (pg:debug (strcat "Read " (itoa (strlen text)) " characters."))
          (setq data (pg:json-parse text))

          (cond
            ((not (listp data))
              (pg:debug "Top-level JSON parse did not return an object list.")
              (prompt "\nUnable to parse JSON file.")
            )
            (T
              (setq meta (pg:json-get data "meta"))
              (setq format (pg:string (pg:json-get meta "format") ""))
              (setq placementsPair (assoc "placements" data))
              (setq placements (if placementsPair (cdr placementsPair) nil))
              (setq wallsPair (assoc "walls" data))
              (setq walls (if wallsPair (cdr wallsPair) nil))
              (setq doorsPair (assoc "doors" data))
              (setq doors (if doorsPair (cdr doorsPair) nil))
              (setq placedCount 0)
              (setq skippedCount 0)
              (setq wallCount 0)
              (setq doorCount 0)

              (if (= format "planetgen_spa_layout_export")
                (progn
                  (pg:debug "Detected spa layout export.")
                  (if (listp walls)
                    (progn
                      (pg:debug (strcat "Found " (itoa (length walls)) " wall entries."))
                      (foreach wall walls
                        (if (pg:draw-wall wall)
                          (setq wallCount (1+ wallCount))
                        )
                      )
                    )
                    (pg:debug "Spa JSON does not contain a walls array.")
                  )
                  (if (listp doors)
                    (progn
                      (pg:debug (strcat "Found " (itoa (length doors)) " door entries."))
                      (foreach door doors
                        (if (pg:draw-door door)
                          (setq doorCount (1+ doorCount))
                        )
                      )
                    )
                    (pg:debug "Spa JSON does not contain a doors array.")
                  )
                  (if (listp placements)
                    (progn
                      (pg:debug (strcat "Found " (itoa (length placements)) " placement entries."))
                      (foreach item placements
                        (if (pg:align-inserted-block (pg:insert-placement item) item)
                          (setq placedCount (1+ placedCount))
                          (setq skippedCount (1+ skippedCount))
                        )
                      )
                    )
                    (pg:debug "Spa JSON does not contain a placements array; continuing with geometry only.")
                  )
                  (prompt
                    (strcat
                      "\nGEN complete. Drew "
                      (itoa wallCount)
                      " walls, "
                      (itoa doorCount)
                      " doors, placed "
                      (itoa placedCount)
                      " blocks, skipped "
                      (itoa skippedCount)
                      "."
                    )
                  )
                )
                (cond
                  ((null placementsPair)
                    (pg:debug "Top-level JSON object does not contain a placements key.")
                    (prompt "\nJSON parse completed, but placements was not found. Check the parser output.")
                  )
                  ((not (listp placements))
                    (pg:debug "placements exists, but is not a list.")
                    (prompt "\nJSON file does not contain a placements array.")
                  )
                  (T
                    (pg:debug (strcat "Found " (itoa (length placements)) " placement entries."))
                    (foreach item placements
                      (if (pg:insert-placement item)
                        (setq placedCount (1+ placedCount))
                        (setq skippedCount (1+ skippedCount))
                      )
                    )
                    (prompt
                      (strcat
                        "\nGEN complete. Placed "
                        (itoa placedCount)
                        ", skipped "
                        (itoa skippedCount)
                        "."
                      )
                    )
                  )
                )
              )
            )
          )
        )
      )
    )
  )
  (princ)
)
