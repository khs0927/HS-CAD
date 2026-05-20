(defun c:ZW_SELECT_BY_LAYER (/ lname ss)
  (setq lname (getstring "
Layer name: "))
  (setq ss (ssget "X" (list (cons 8 lname))))
  (if ss (sssetfirst nil ss))
  (princ)
)
