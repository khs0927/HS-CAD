;;; ------------------------------------------------------------------------
;;; xiCAD legacy alias compatibility wrappers
;;; Auto-generated from the frozen 357 audit and xiCAD 5.50 evidence.
;;; Safe default profile: aliases that are unoccupied in xiCAD 5.50 only.
;;; These wrappers preserve interactive legacy behavior; they are not
;;; headless MCP adapters and are not production evidence.
;;; ------------------------------------------------------------------------

;;; 1 -> LL / xiSelOff
(defun C:1 (/) (xiSelOff) (princ))

;;; 2 -> LF / xiSelLayerOn
(defun C:2 (/) (xiSelLayerOn) (princ))

;;; 3 -> LO / xiLayeron
(defun C:3 (/) (xiLayeron) (princ))

;;; BBB -> B / xiBreakMulti
(defun C:BBB (/) (xiBreakMulti) (princ))

;;; CE -> CEN / xiCenter
(defun C:CE (/) (xiCenter) (princ))

;;; DE -> CC / xiConDim
(defun C:DE (/) (xiConDim) (princ))

;;; EW -> LE / xiSetCLayer
(defun C:EW (/) (xiSetCLayer) (princ))

;;; FF -> FL / xiFilletL
(defun C:FF (/) (xiFilletL) (princ))

;;; LOC -> LFC / xiLayerOnColor
(defun C:LOC (/) (xiLayerOnColor) (princ))

;;; LT -> LOO / xiLayerThaw
(defun C:LT (/) (xiLayerThaw) (princ))

;;; MK -> MSK / xiMask
(defun C:MK (/) (xiMask) (princ))

;;; Q11 -> Q1 / xiBlockLibrary
(defun C:Q11 (/) (xiBlockLibrary) (princ))

;;; WE -> PET / xiPolyEndTab
(defun C:WE (/) (xiPolyEndTab) (princ))

;;; WQ -> OC / xiOffsetAndClose
(defun C:WQ (/) (xiOffsetAndClose) (princ))

;;; XX -> X / xiX
(defun C:XX (/) (xiX) (princ))

(princ "\n[xiCAD] Loaded 15 statically validated legacy aliases.")
(princ)
