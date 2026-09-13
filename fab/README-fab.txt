eswitch rev A - fabrication notes
==================================
Layers:            4 (F.Cu, In1.Cu=GND plane, In2.Cu=PWR, B.Cu)
Board size:        181.0 x 57.5 mm
Thickness:         1.6 mm
Copper weight:     2 oz outer, 1 oz inner (high-current bus and load strips on the outer layers)
Material:          FR-4 TG150 or better
Surface finish:    ENIG preferred (HASL acceptable)
Solder mask:       green; silkscreen white
Min track/space:   0.15 / 0.20 mm
Min via:           0.5 mm pad / 0.3 mm drill (module thermal vias 0.2 mm drill)
Drill file:        Excellon, PTH and NPTH merged (eswitch.drl), plus .drl map
Gerber layer map:  eswitch-F_Cu / eswitch-GND (In1) / eswitch-PWR (In2) / eswitch-B_Cu,
                   F/B_Mask, F/B_Paste, F/B_Silkscreen, Edge_Cuts, eswitch-job.gbrjob
Assembly:          all SMD parts on the BOTTOM side; through-hole parts on the top are
                   hand-soldered (fuse clips, terminal block, screw terminals, header).
