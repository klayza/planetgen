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

(defun pg:insert-placement (item / blockName point x y z sx sy rot itemType)
  (setq itemType (pg:string (pg:json-get item "type") "UNKNOWN"))
  (setq blockName (pg:string (pg:json-get item "block_name") ""))
  (setq point (pg:json-get item "insertion_point"))
  (setq x (pg:number (pg:json-get point "x") 0.0))
  (setq y (pg:number (pg:json-get point "y") 0.0))
  (setq z (pg:number (pg:json-get point "z") 0.0))
  (setq rot (pg:number (pg:json-get item "rotation") 0.0))
  (setq sx (pg:json-get item "scale"))
  (setq sy sx)

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
      (command
        "_.-INSERT"
        blockName
        (list x y z)
        (pg:number (pg:json-get sx "x") 1.0)
        (pg:number (pg:json-get sy "y") 1.0)
        rot
      )
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
      T
    )
  )
)

(defun c:gen ( / path text data placements placementsPair placedCount skippedCount)
  (setq path (getfiled "Select Planetgen layout JSON" "" "json" 16))

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
          (setq placementsPair (assoc "placements" data))
          (setq placements (if placementsPair (cdr placementsPair) nil))

          (cond
            ((not (listp data))
              (pg:debug "Top-level JSON parse did not return an object list.")
              (prompt "\nUnable to parse JSON file.")
            )
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
              (setq placedCount 0)
              (setq skippedCount 0)
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
  (princ)
)
