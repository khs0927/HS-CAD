(defun c:ZW_CLEAN_LAYERS ()
  (command "_.-PURGE" "_LA" "*" "_N")
  (princ)
)
