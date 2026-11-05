(vl-load-com)

(defun hscad:probe-xicad-runtime (key-file output-file / input output line pos alias seen symbol-name)
  (setq input (open key-file "r"))
  (setq output (open output-file "w"))
  (if (and input output)
    (progn
      (setq seen nil)
      (while (setq line (read-line input))
        (setq line (vl-string-trim " \t\r\n" line))
        (if (and
              (> (strlen line) 0)
              (not (wcmatch line "`*Sec*"))
              (setq pos (vl-string-search ";" line))
            )
          (progn
            (setq alias (vl-string-trim " \t" (substr line 1 pos)))
            (if (and (> (strlen alias) 0) (not (assoc (strcase alias) seen)))
              (progn
                (setq seen (cons (cons (strcase alias) T) seen))
                (setq symbol-name (strcat "C:" alias))
                (write-line
                  (strcat alias "\t" (if (atoms-family 1 (list symbol-name)) "1" "0"))
                  output
                )
              )
            )
          )
        )
      )
      (close input)
      (close output)
      (setvar "USERS1" "HSCAD_PROBE_DONE")
    )
    (progn
      (if input (close input))
      (if output (close output))
      (setvar "USERS1" "HSCAD_PROBE_FILE_OPEN_FAILED")
    )
  )
  (princ)
)

(princ)
