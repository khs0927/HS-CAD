;;; ZWEXTRACTTEXTS - print TEXT/MTEXT handles, layers and strings.
(defun c:ZWEXTRACTTEXTS (/ ss i ent obj txt lay hnd)
  (vl-load-com)
  (setq ss (ssget "X" '((0 . "TEXT,MTEXT"))))
  (if ss
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq ent (ssname ss i))
        (setq obj (vlax-ename->vla-object ent))
        (setq txt (vla-get-TextString obj))
        (setq lay (vla-get-Layer obj))
        (setq hnd (vla-get-Handle obj))
        (princ (strcat "\n" hnd " | " lay " | " txt))
        (setq i (1+ i))))
    (princ "\nNo text objects found."))
  (princ))
