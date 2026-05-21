(defun c:AnalyzeDrawing ( / ss i ent dxf typ lay blkname flags closedPoly openPoly roomTexts typesList layersList blocksList assocTyp assocLay assocBlk txt pair roomCount file outPath total)
  (setq outPath "C:/zwcad-ai-modifier-xicad-next-complete/zwcad-ai-modifier/audit.txt")
  (setq file (open outPath "w"))
  
  (if (not file)
    (progn
      (princ "\nError: Could not open output file for writing.")
    )
    (progn
      (write-line "=== LISP DRAWING AUDIT ===" file)
      
      (setq ss (ssget "x" '((410 . "Model"))))
      (if ss
        (progn
          (setq i 0)
          (setq total (sslength ss))
          (write-line (strcat "Total Objects: " (itoa total)) file)
          
          (setq typesList '())
          (setq layersList '())
          (setq blocksList '())
          (setq closedPoly 0)
          (setq openPoly 0)
          (setq roomTexts '())
          
          (while (< i total)
            (setq ent (ssname ss i))
            (if ent
              (progn
                (setq dxf (entget ent))
                (if dxf
                  (progn
                    (setq typ (cdr (assoc 0 dxf)))
                    (setq lay (cdr (assoc 8 dxf)))
                    
                    (if (and typ lay (stringp typ) (stringp lay))
                      (progn
                        ; 1. Increment type count
                        (setq assocTyp (assoc typ typesList))
                        (if assocTyp
                          (setq typesList (subst (cons typ (1+ (cdr assocTyp))) assocTyp typesList))
                          (setq typesList (cons (cons typ 1) typesList))
                        )
                        
                        ; 2. Increment layer count
                        (setq assocLay (assoc lay layersList))
                        (if assocLay
                          (setq layersList (subst (cons lay (1+ (cdr assocLay))) assocLay layersList))
                          (setq layersList (cons (cons lay 1) layersList))
                        )
                        
                        ; 3. Polyline closed check
                        (if (= typ "LWPOLYLINE")
                          (progn
                            (setq flags (cdr (assoc 70 dxf)))
                            (if (and flags (integerp flags) (= (logand flags 1) 1))
                              (setq closedPoly (1+ closedPoly))
                              (setq openPoly (1+ openPoly))
                            )
                          )
                        )
                        
                        ; 4. Block insert check
                        (if (= typ "INSERT")
                          (progn
                            (setq blkname (cdr (assoc 2 dxf)))
                            (if (and blkname (stringp blkname))
                              (progn
                                (setq assocBlk (assoc blkname blocksList))
                                (if assocBlk
                                  (setq blocksList (subst (cons blkname (1+ (cdr assocBlk))) assocBlk blocksList))
                                  (setq blocksList (cons (cons blkname 1) blocksList))
                                )
                              )
                            )
                          )
                        )
                        
                        ; 5. Texts check
                        (if (or (= typ "TEXT") (= typ "MTEXT"))
                          (progn
                            (setq txt (cdr (assoc 1 dxf)))
                            (if (and txt (stringp txt))
                              (progn
                                (if (or (wcmatch (strcase lay) "*ROOM*")
                                        (wcmatch (strcase lay) "*실*")
                                        (wcmatch (strcase lay) "*NAME*")
                                        (wcmatch (strcase lay) "*XI*"))
                                  (setq roomTexts (cons (cons txt lay) roomTexts))
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
            )
            (setq i (1+ i))
          )
          
          (write-line "\n--- Entity Counts ---" file)
          (foreach pair typesList
            (write-line (strcat (car pair) ": " (itoa (cdr pair))) file)
          )
          
          (write-line "\n--- Layer Counts ---" file)
          (foreach pair layersList
            (write-line (strcat (car pair) ": " (itoa (cdr pair))) file)
          )
          
          (write-line "\n--- Block Counts ---" file)
          (foreach pair blocksList
            (write-line (strcat (car pair) ": " (itoa (cdr pair))) file)
          )
          
          (write-line "\n--- Polyline Quality ---" file)
          (write-line (strcat "Closed Count: " (itoa closedPoly)) file)
          (write-line (strcat "Open Count: " (itoa openPoly)) file)
          
          (write-line "\n--- Room Texts ---" file)
          (setq roomCount 0)
          (foreach pair roomTexts
            (if (< roomCount 150)
              (write-line (strcat (car pair) " (Layer: " (cdr pair) ")") file)
            )
            (setq roomCount (1+ roomCount))
          )
        )
        (write-line "No objects found in Model Space" file)
      )
      
      (close file)
      (princ "\nDrawing analysis completed successfully by AutoLISP!")
    )
  )
  (princ)
)
