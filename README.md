# PLANETGEN

The generative design approach to automating planet fitness floorplan design



```
do these items:
1. add a button to the app to export the current layout into a json file.
2. write an autocad lisp script that will load the json file and place everything in the layout. use the command gen. then select json file.

reference this script that can place machines by their name:
```
(defun c:gen ( / blockMap input data code x y blockName)
  ;; alias -> actual block name already in this drawing
  (setq blockMap
    '(
      ("TR" . "Treadmill (T5X-5PL-PF)")
    )
  )

  ;; user enters: tr 50 100
  (setq input (getstring T "\nEnter <code x y> (example: tr 50 100): "))

  (if (or (null input) (= input ""))
    (prompt "\nNo input provided.")
    (progn
      (setq data (vl-catch-all-apply 'read (list (strcat "(" input ")"))))

      (if (vl-catch-all-error-p data)
        (prompt "\nInvalid format. Example: tr 50 100")
        (progn
          (if (< (length data) 3)
            (prompt "\nInvalid input. Example: tr 50 100")
            (progn
              (setq code (strcase (vl-symbol-name (car data))))
              (setq x (float (cadr data)))
              (setq y (float (caddr data)))

              (setq blockName (cdr (assoc code blockMap)))

              (cond
                ((null blockName)
                  (prompt (strcat "\nUnknown equipment code: " code))
                )
                ((not (tblsearch "BLOCK" blockName))
                  (prompt (strcat "\nBlock not found in drawing: " blockName))
                )
                (T
                  (command "_.-INSERT" blockName (list x y 0.0) 1.0 1.0 0.0)
                  (prompt
                    (strcat
                      "\nPlaced "
                      code
                      " at ("
                      (rtos x 2 2)
                      ", "
                      (rtos y 2 2)
                      ")."
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
  (princ)
)```


add the appropriate block name references to [equipment.json](src/equipment.json)  
only for the machines already in the json.
```
Command: LISTBLOCKS

_ArchTick

TUB-flat-2

ELLIPSE-flat-7

SINKB-flat-6

WALLWC-flat-1

FXTT

Shoulder Press (MTSSP-PF)

Row (MTSRW-PF)

Front Press (MTSFP-PF)

Incline Press (MTSIP-PF)

Chest Press (MTSCP-PF)

Ab (MTSAB-PF)

90 - CV (PF90CV-RP-PF)

90 - VC (PF90CV-RP-PF)

S3 - 1 Bay S3 (CORE-PF)

S3 - 2 Bay S3 (CORE-PF)

S3 - 3 Bay (S3 CORE-PF)

Ab Coaster (CTL-P)

AbCompany Bench (TAB01-P)

V - Crunch (AB-103-PF)

Target Ab (TGT-P)

Total Gym (6000-P1)

True Stretch (800SS)

Stretching Area

Beauty Bell Rack (BBUSET RACK)

Barbell Rack (BARBELL SET)

Accessory (ACC RACK W. HANDLES)

SciFit Rec. (SONE04-PF-4P1L-PF)

SciFit Up. (PRO1033-PF-4P1L-PF)

Floor Mat Rack (ST-Mat-Rack)

Matrix Storage Rack (GFTORG-5PL-PF)

Precor 6' Single Bay Storage (PF175-6)

Wall Mat Rack

CLEARANCE

HANDISYM

Ascent (ALB5X-PF-4PL)

Ascent Full (A5X-4PL-PF)

Bike Rec. (R5X-5PL-PF)

Bike Up. (U5X-5PL-PF)

Elliptical (E5X-5PL-PF)

Rower (ROWER-5PL-PF)

Stepmill (C5X-5PL-PF)

Treadmill (T5X-5PL-PF)

Ab w- Graduated Stack (G7S51-5PL-PF)

Abdominal (G3S51-5PL-PF)

Back Extension (G7S52-5PL-PF)

Bicep Curl (G3S40-5PL-PF)

Calf Extension (G7S77-5PL-PF)

Chest Press (G7S13-5PL-PF)

Bicep Curl (G7S40-5PL-PF)

Lat Pull down (G7S33-5PL-PF)

Leg Extension (G7S71-5PL-PF)

Leg Press (G7S70-5PL-PF)

Shoulder Press (G7S23-5PL-PF)

Pec fly. rear Delt (G7S22-5PL-PF)

Row. Rear Deltoid (G7S34-5PL-PF)

Seated Leg Curl (G7S72-5PL-PF)

Triceps Curl (G3S45-5PL-PF)

Triceps Press (G7S42-5PL-PF)

Aura Ab Crunch (G3S51-5PL-PF)

Aura Arm Curl (G3S40-5PL-PF)

Calf Press (G3S77-5PL-PF)

Aura Chest Press (G3S13-5PL-PF)

Aura Lat. Raise (G3S21-5PL-PF)

Aura seated Leg Curl (G3S72-5PL-PF)

Aura Leg Extension (G3S71-5PL-PF)

Aura Leg Press (G3S70-5PL-PF)

Aura Pulldown (G3S33-5PL-PF)

Aura Seated Row (G3S34-5PL-PF)

Aura Shoulder Press (G3S23-5PL-PF)

Aura Tricep Ext. (G3S45-5PL-PF)

Smith Machine (MG-PL62-5PL-PF)

Ab w- Graduated Stack (VS-S53-PH-5PL-PF)

Bicep Curl (VS-S40-5PL-PF)

Chest Press (VS-S13-5PL-PF)

Leg Press (VS-S70-5PL-PF)

Pull Down (VS-S33-5PL-PF)

Row. Rear Deltoid (VS-S34-5PL-PF)

Over Head Press (VS-S23-5PL-PF)

Step (MG-SUP-5PL-PF)

Triceps Extension (VS-S42-5PL-PF)

Prone Leg Curl (VS-S72-5PL-PF)

Leg Extension (VS-S71-5PL-PF)

Decline. Ab Board (G3FW83-5PL-PF)

Flat Adj. Incline Bench (MG-A82-5PL-PF)

Flat Bench (G3FW81-5PL-PF)

Dumbbell Rack (G3-FW91-5PL-PF)

Plate Loaded Leg Press (MG-PL70-5PL-PF)

Standard Matrix Towers

Matrix Towers Alt. Configuration 1

Matrix Towers Alt. Configuration 2

Matrix Towers Alt. Configuration 3

Matrix Towers Alt. Configuration 4

Matrix Towers Alt. Configuration 5

Matrix Towers Alt. Configuration 6

Matrix Towers Alt. Configuration 7

Dip Chin Assist (G3S60-5PL-PF)

Glute (G7S78-5PL-PF)

Hip Abductor (G7S75-5PL-PF)

Hip Adductor (G7S74-5PL-PF)

Lateral Raise (G7S21-5PL-PF)

Prone Leg Curl (G7S73-5PL-PF)

Torso Rotation (G7S55-5PL-PF)

Weight Tree (G3-FW94-5PL-PF)

Xult 3 Ball Rack (X3BSR-PF)

*U105

HM5A

Ab w- Graduated Stack (21090-PF)

Body Weight Back Extension (BWBE-PF)

Dip Leg Ab Chair (16180-PF)

LF Optima Stretch (OP-FS)

*U111

Insignia Glute

XL (PF360XL-RP-PF)

XS (PF360XS-RP-PF)

XM (PF360XM-RP-PF)

T (PF360T-RP-PF)

Dual Adj Pulley (CMDAP-PF)

Duel Adj. Pulley (VS-VFT-5PL-PF)

Connexus Crest- LeftFT

Matrix Connexus Hub

Connexus SM

Connexus MED

Connexus LG

Connexus Edge

Connexus Edge-2

Connexus Edge-3

Dip leg Ab Chair (MG-A63C-5PL-PF)

Dip Leg Ab Chair

Hip Adductor - Abductor (VS-S74)

Magnum Half Rach MG-A690 with Landmine

Magnum-Hack Squat-MG-PL71

Magnum-Seated Calf-MG-PL77

Magnum_Incline_bench_MG-PL14

Magnum_Shoulder_MG-PL23

Magnum_Squat_Lunge_MG-PL79

M Plate Loaded Row

M Plate Loaded Lat Pulldown

Magnum_Glute_Trainer_MG-PL78

Magnum-Preacher Curl-MG-A62

Magnum-Vertical Bench-MG-PL12

M Plate Loaded Horizontal Bench Press

M Plate Loaded Standing Calf

Total Gym Pullup

FitBench One

Turf

M Elevate Rower

M AirBike

Command:```
```