;;; ZWLOADXICAD - minimal XiCAD bootstrap loader.
;;; Usage in ZWCAD command line:
;;;   (setq *zwai-xicad-root* "C:/xicad")
;;;   ZWLOADXICAD
(defun c:ZWLOADXICAD (/ root loader1 loader2 zwlsp)
  (vl-load-com)
  (setq root (if (boundp '*zwai-xicad-root*) *zwai-xicad-root* ""))
  (if (= root "")
    (progn (princ "\nSet *zwai-xicad-root* first. Example: (setq *zwai-xicad-root* \"C:/xicad\")") (princ))
    (progn
      (setq loader1 (strcat root "/Lisp/xi.zelx"))
      (setq loader2 (strcat root "/Lisp/xi.fas"))
      (setq zwlsp (strcat root "/_ZWCad/zwcad.lsp"))
      (if (findfile zwlsp) (load zwlsp))
      (cond
        ((findfile loader1) (load loader1))
        ((findfile loader2) (load loader2))
        (T (princ "\nNo XiCAD xi.zelx or xi.fas loader found.")))
      (princ "\nZWLOADXICAD completed.")))
  (princ))
