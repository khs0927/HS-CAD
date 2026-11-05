;;; ------------------------------------------------------------------------
;;; xiCAD explicit legacy collision profile
;;; Auto-generated from the frozen 357 audit and xiCAD 5.50 evidence.
;;; NOT loaded by default. Loading this file deliberately overrides current aliases.
;;; These wrappers preserve interactive legacy behavior; they are not
;;; headless MCP adapters and are not production evidence.
;;; ------------------------------------------------------------------------

;;; LF currently means xiSelLayerOn in 5.50. This profile restores the
;;; frozen legacy LF meaning xiSelFreeze. Current layer-on behavior remains
;;; available through generated alias 2 -> xiSelLayerOn.

;;; LF -> LLL / xiSelFreeze
(defun C:LF (/) (xiSelFreeze) (princ))

(princ "\n[xiCAD] Loaded 1 explicit legacy alias override.")
(princ)
