(vl-load-com)

(defun gd:string (value fallback)
  (if (= (type value) 'STR) value fallback)
)

(defun gd:number (value fallback)
  (if (numberp value) value fallback)
)

(defun gd:abs (value)
  (if (< value 0.0)
    (- value)
    value
  )
)

(defun gd:safe-get (obj method fallback / result)
  (setq result (vl-catch-all-apply method (list obj)))
  (if (vl-catch-all-error-p result)
    fallback
    result
  )
)

(defun gd:block-name (obj / effective raw)
  (setq effective (gd:safe-get obj 'vla-get-EffectiveName ""))
  (setq raw (gd:safe-get obj 'vla-get-Name ""))
  (cond
    ((and (/= effective "") (/= effective raw))
      (strcat "Block=" effective " (raw=" raw ")")
    )
    ((/= effective "")
      (strcat "Block=" effective)
    )
    ((/= raw "")
      (strcat "Block=" raw)
    )
    (T
      "Block=<unknown>"
    )
  )
)

(defun gd:com-array->list (value / unwrapped)
  (setq unwrapped (vl-catch-all-apply 'vlax-variant-value (list value)))
  (if (vl-catch-all-error-p unwrapped)
    (vlax-safearray->list value)
    (vlax-safearray->list unwrapped)
  )
)

(defun gd:get-bounding-box-points (obj / minPt maxPt)
  (vla-GetBoundingBox obj 'minPt 'maxPt)
  (list
    (gd:com-array->list minPt)
    (gd:com-array->list maxPt)
  )
)

(defun gd:fmt-num (value)
  (rtos (gd:number value 0.0) 2 3)
)

(defun gd:fmt-pt2 (pt)
  (strcat "(" (gd:fmt-num (car pt)) ", " (gd:fmt-num (cadr pt)) ")")
)

(defun gd:rotation-degrees (obj / radians)
  (setq radians (gd:safe-get obj 'vla-get-Rotation 0.0))
  (* 180.0 (/ radians pi))
)

(defun gd:insert-debug-lines (obj / ins bbox minPt maxPt centerPt width depth rawName effectiveName)
  (setq ins (vlax-get obj 'InsertionPoint))
  (setq bbox (gd:get-bounding-box-points obj))
  (setq minPt (car bbox))
  (setq maxPt (cadr bbox))
  (setq centerPt
    (list
      (/ (+ (car minPt) (car maxPt)) 2.0)
      (/ (+ (cadr minPt) (cadr maxPt)) 2.0)
    )
  )
  (setq width (gd:abs (- (car maxPt) (car minPt))))
  (setq depth (gd:abs (- (cadr maxPt) (cadr minPt))))
  (setq rawName (gd:safe-get obj 'vla-get-Name ""))
  (setq effectiveName (gd:safe-get obj 'vla-get-EffectiveName rawName))
  (list
    (strcat "[GENCAL] Block=" effectiveName)
    (strcat "[GENCAL] RawName=" rawName)
    (strcat "[GENCAL] Insertion=" (gd:fmt-pt2 ins))
    (strcat "[GENCAL] Rotation=" (gd:fmt-num (gd:rotation-degrees obj)) " deg")
    (strcat "[GENCAL] BBoxMin=" (gd:fmt-pt2 minPt))
    (strcat "[GENCAL] BBoxMax=" (gd:fmt-pt2 maxPt))
    (strcat "[GENCAL] BBoxCenter=" (gd:fmt-pt2 centerPt))
    (strcat "[GENCAL] BBoxSize=" (gd:fmt-num width) " x " (gd:fmt-num depth))
  )
)

(defun gd:text-value (edata / value)
  (setq value (cdr (assoc 1 edata)))
  (if value
    (strcat "Text=\"" value "\"")
    "Text=<empty>"
  )
)

(defun gd:entity-label (ename / edata entityType layer handle obj)
  (setq edata (entget ename))
  (setq entityType (gd:string (cdr (assoc 0 edata)) "UNKNOWN"))
  (setq layer (gd:string (cdr (assoc 8 edata)) ""))
  (setq handle (gd:string (cdr (assoc 5 edata)) ""))

  (cond
    ((= entityType "INSERT")
      (setq obj (vlax-ename->vla-object ename))
      (strcat
        entityType
        " | "
        (gd:block-name obj)
        " | Layer="
        layer
        " | Handle="
        handle
      )
    )
    ((member entityType '("TEXT" "MTEXT" "ATTRIB" "ATTDEF"))
      (strcat
        entityType
        " | "
        (gd:text-value edata)
        " | Layer="
        layer
        " | Handle="
        handle
      )
    )
    (T
      (strcat
        entityType
        " | Layer="
        layer
        " | Handle="
        handle
      )
    )
  )
)

(defun c:gencal ( / ename edata entityType obj lines)
  (prompt "\nSelect one inserted block to inspect.")
  (setq ename (car (entsel)))
  (if (null ename)
    (prompt "\nNo entity selected.")
    (progn
      (setq edata (entget ename))
      (setq entityType (gd:string (cdr (assoc 0 edata)) ""))
      (if (/= entityType "INSERT")
        (prompt "\nSelected entity is not a block insert.")
        (progn
          (setq obj (vlax-ename->vla-object ename))
          (setq lines (gd:insert-debug-lines obj))
          (foreach line lines
            (prompt (strcat "\n" line))
          )
        )
      )
    )
  )
  (princ)
)

(defun c:gendebug ( / ss idx ename count)
  (prompt "\nSelect entities to inspect.")
  (setq ss (ssget))

  (if (null ss)
    (prompt "\nNo entities selected.")
    (progn
      (setq idx 0)
      (setq count (sslength ss))
      (prompt (strcat "\n[GENDEBUG] Selected " (itoa count) " item(s)."))
      (while (< idx count)
        (setq ename (ssname ss idx))
        (prompt (strcat "\n[GENDEBUG] " (itoa (1+ idx)) ": " (gd:entity-label ename)))
        (setq idx (1+ idx))
      )
    )
  )
  (princ)
)
