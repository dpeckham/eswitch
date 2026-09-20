#!/usr/bin/env python3
"""Generate JLC's requested impedance specification image for the CAM ZIP."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def make_request(destination):
    image=Image.new('RGB',(1800,1200),'white');draw=ImageDraw.Draw(image)
    regular='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    font=ImageFont.truetype(regular,27);small=ImageFont.truetype(regular,23)
    title=ImageFont.truetype(bold,42)
    draw.text((60,45),'eswitch Rev C - USB impedance request',font=title,fill='#153554')
    lines=[
        'Target: 90 ohm differential, +/-10%; non-coplanar differential pair.',
        'Signal: L4 / B.Cu. Reference: L3 / In2.Cu (GND beneath USB pair).',
        'Nets: USB_D+ and USB_D-; J4 USB-C to R2/R3 near U10 ESP32.',
        'Nominal straight geometry: width 0.235 mm; edge-to-edge gap 0.215 mm.',
        'Stackup: JLC041622-3313; 4 layers; ENIG; 2 oz OUTER and INNER.',
        'Nominal board 1.6 mm (stackup 1.59 mm); board 334 x 172 mm.',
        'Copper L1/L2/L3/L4: 0.070 / 0.061 / 0.061 / 0.070 mm.',
        'Dielectric L1-L2 / L2-L3 / L3-L4: 0.1835 / 0.9600 / 0.1835 mm.',
        'Position from upper-left outline corner, top-view coordinates:',
        '    x = 6.3 to 26.3 mm; y = 18.4 to 52.5 mm.',
        'Short component pad escapes and USB_MCU_D+/- stubs are excluded.',
        'Return any proposed geometry/stackup change for production-file review.',
    ]
    for index,line in enumerate(lines):draw.text((60,125+index*46),line,font=font,fill='#153554')
    x,y,scale=90,755,2.0
    draw.rectangle((x,y,x+334*scale,y+172*scale),outline='#153554',width=4)
    draw.rectangle((x+6.3*scale,y+18.4*scale,x+26.3*scale,y+52.5*scale),fill='#ce5b30')
    draw.text((x+90,y+36),'USB pair location',font=small,fill='#ce5b30')
    draw.line((x+26.3*scale,y+36*scale,x+85,y+49),fill='#ce5b30',width=3)
    draw.text((815,780),'Board diagram: top-view projection',font=font,fill='#153554')
    draw.text((815,825),'Origin (0, 0) at upper-left outline corner.',font=small,fill='#153554')
    draw.text((815,867),'The pair is on the bottom copper layer.',font=small,fill='#153554')
    draw.text((815,934),'Use all supplied Gerber layers and',font=small,fill='#153554')
    draw.text((815,970),'separate plated / non-plated drill files.',font=small,fill='#153554')
    image.save(Path(destination)/'USB-impedance-request.jpg',quality=95,subsampling=0)


if __name__=='__main__':
    import sys
    make_request(Path(sys.argv[1]))
