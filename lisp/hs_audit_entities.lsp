;;; HS_AUDIT_ENTITIES
;;; CAD-internal modelspace audit for large drawings.
;;; Writes TSV rows: section key value

(defun hs-inc (key rows / found pair)
  (setq found (assoc key rows))
  (if found
    (subst (cons key (1+ (cdr found))) found rows)
    (cons (cons key 1) rows)
  )
)

(defun HS_AUDIT_ENTITIES (outPath / ss i ent dxf typ lay blk file entities layers blocks pair)
  (setq file (open outPath "w"))
  (if (not file)
    (progn
      (princ "\nHS_AUDIT_ENTITIES: could not open output file.")
    )
    (progn
      (write-line "section\tkey\tvalue" file)
      (setq entities '())
      (setq layers '())
      (setq blocks '())
      (setq ss (ssget "X" '((410 . "Model"))))
      (if ss
        (progn
          (setq i 0)
          (while (< i (sslength ss))
            (setq ent (ssname ss i))
            (setq dxf (entget ent))
            (setq typ (cdr (assoc 0 dxf)))
            (setq lay (cdr (assoc 8 dxf)))
            (if typ (setq entities (hs-inc typ entities)))
            (if lay (setq layers (hs-inc lay layers)))
            (if (= typ "INSERT")
              (progn
                (setq blk (cdr (assoc 2 dxf)))
                (if blk (setq blocks (hs-inc blk blocks)))
              )
            )
            (setq i (1+ i))
          )
        )
      )
      (foreach pair entities
        (write-line (strcat "entity\t" (car pair) "\t" (itoa (cdr pair))) file)
      )
      (foreach pair layers
        (write-line (strcat "layer\t" (car pair) "\t" (itoa (cdr pair))) file)
      )
      (foreach pair blocks
        (write-line (strcat "block\t" (car pair) "\t" (itoa (cdr pair))) file)
      )
      (close file)
      (princ (strcat "\nHS_AUDIT_ENTITIES wrote: " outPath))
    )
  )
  (princ)
)
