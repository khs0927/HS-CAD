;;; ZWCOUNTBLOCKS - count block references in the current drawing.
(defun c:ZWCOUNTBLOCKS (/ ss i ent obj name counts item)
  (vl-load-com)
  (setq counts '())
  (setq ss (ssget "X" '((0 . "INSERT"))))
  (if ss
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq ent (ssname ss i))
        (setq obj (vlax-ename->vla-object ent))
        (setq name (vla-get-EffectiveName obj))
        (setq item (assoc name counts))
        (if item
          (setq counts (subst (cons name (1+ (cdr item))) item counts))
          (setq counts (cons (cons name 1) counts)))
        (setq i (1+ i)))
      (foreach pair counts (princ (strcat "\n" (car pair) ": " (itoa (cdr pair))))))
    (princ "\nNo block references found."))
  (princ))

;;; Alias kept for typo-tolerant workflows.
(defun c:ZWCOUNTTBLOCKS () (c:ZWCOUNTBLOCKS))
