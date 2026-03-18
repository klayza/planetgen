(defun c:gen ( / blockMap input data code x y blockName)
  ;; alias -> actual block name already in this drawing
  (setq blockMap
    '(
      ("TR" . "41")
    )
  )

  ;; user enters: tr 50 100
  (setq input (getstring T "\nEnter <code x y> (example: tr 50 100): "))

  (if (or (null input) (= input ""))
    (prompt "\nNo input provided.")
    (progn
      (setq data (vl-catch-all-apply 'read (list (strcat "(" input ")"))))

      (if (vl-catch-all-error-p data)
        (prompt "\nInvalid format. Example: tr 50 100")
        (progn
          (if (< (length data) 3)
            (prompt "\nInvalid input. Example: tr 50 100")
            (progn
              (setq code (strcase (vl-symbol-name (car data))))
              (setq x (float (cadr data)))
              (setq y (float (caddr data)))

              (setq blockName (cdr (assoc code blockMap)))

              (cond
                ((null blockName)
                  (prompt (strcat "\nUnknown equipment code: " code))
                )
                ((not (tblsearch "BLOCK" blockName))
                  (prompt (strcat "\nBlock not found in drawing: " blockName))
                )
                (T
                  (command "_.-INSERT" blockName (list x y 0.0) 1.0 1.0 0.0)
                  (prompt
                    (strcat
                      "\nPlaced "
                      code
                      " at ("
                      (rtos x 2 2)
                      ", "
                      (rtos y 2 2)
                      ")."
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