#!/usr/bin/env python3
"""Generate the new schematic and a dated, explicitly provisional BOM estimate."""
import csv
from decimal import Decimal, ROUND_HALF_UP
import json
import os
import shutil
from pathlib import Path
import sys
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
mac_data = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport')
if mac_data.is_dir():
    os.environ.setdefault('KICAD_STOCK_DATA_HOME', str(mac_data))
sys.path.insert(0, str(ROOT / 'tools'))
import gen_sch as sch
from sexp import S, Sym, dump
import circuit
import kicad_env

PROJECT = 'eswitch-simple'


def schematic():
    # Use only the existing low-level drawing/library parser. The old circuit
    # builder, old annotations, and old release metadata are never invoked.
    # Make the editable project self-contained, including the custom 3D models.
    # Once copied, local assets are authoritative; do not overwrite local edits.
    local_lib = HERE / 'lib'
    if not local_lib.exists():
        shutil.copytree(ROOT / 'lib', local_lib)
    sch.ROOT = str(HERE)
    sch.PROJECT = PROJECT
    sch.ROOT_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, 'eswitch-simple-draft'))
    sch._uuid_counter[0] = 0
    used = {}
    items = []
    for part in circuit.build():
        symbol = used.setdefault(part.lib_id, sch.load_symbol(part.lib_id))
        pins = sch.symbol_pins(symbol)
        items.append(sch.symbol_instance(part.lib_id, part.ref, part.value, part.footprint,
                     part.at, part.rot, [p[0] for p in pins], part.fields,
                     hide_value=part.ref.startswith('#'), sym=symbol))
        positions = set()
        for pin in pins:
            number, _, _, _, _, _, hidden, kind = pin
            pos, direction = sch.pin_screen(part, pin)
            if pos in positions:
                continue
            net = part.pins.get(number)
            if net is None:
                if not hidden and kind != 'no_connect':
                    items.append(sch.no_connect(pos))
                continue
            positions.add(pos)
            end = tuple(round(v + d * sch.STUB, 4) for v, d in zip(pos, direction))
            items.extend([sch.wire(pos, end), sch.label(net, end, direction)])
    annotations = [
        ('ESWITCH — PROTECTION REVISION CANDIDATE / NOT FOR FABRICATION', (12.7, 17.78), 3),
        ('ESP32-S3: independent IN and DEN for every channel; ADC1 current sense', (330.2, 25.4), 1.5),
        ('USB: battery disconnected for programming. Wi-Fi / BLE / OTA in service.', (330.2, 222.25), 1.5),
        ('AUTO + LOGIC: shared fused LM74800 cutoff. BYPASS: raw battery, no electronics.', (12.7, 232.41), 1.5),
        ('OUTPUTS: pin 1 LOAD+, pin 2 GND; direct-entry screw terminals', (330.2, 246.38), 1.5),
        ('9.5–16 V / 40 A aggregate TARGET. Upstream battery fuse required.', (330.2, 370.84), 1.5),
        ('BYPASS connects raw battery through ONE fuse. Move fuses ONLY unpowered.', (12.7, 365.76), 1.5),
        ('Recovery: REMOVE F10 to isolate AUTO electronics; move load fuses to BYPASS.', (12.7, 373.38), 1.5),
        ('SHARED AUTO/LOGIC PROTECTION — BYPASS remains raw battery', (12.7, 406.4), 2),
        ('Channel LEDs indicate PROFET output, not the BYPASS load terminal.', (330.2, 386.08), 1.5),
    ]
    for n in range(1, 9):
        x, y = 12.7 + (n-1) % 4 * 76.2, 25.4 + (n-1) // 4 * 93.98
        annotations.append((f'CH{n}: AUTO / BYPASS / REMOVE = OFF', (x, y), 1.5))
    items.extend(sch.text(t, xy, size) for t, xy, size in annotations)
    document = S('kicad_sch', S('version', sch.SCH_VERSION), S('generator', 'eeschema'),
                 S('generator_version', '10.0'), S('uuid', sch.ROOT_UUID), S('paper', 'A1'),
                 S('title_block', S('title', 'eswitch simple — passive fuse bypass'),
                     S('date', '2026-10-27'), S('rev', 'PROTO-PWR3')),
                 S('lib_symbols', *used.values()), *items,
                 S('sheet_instances', S('path', '/', S('page', '1'))), S('embedded_fonts', Sym('no')))
    (HERE / f'{PROJECT}.kicad_sch').write_text(dump(document) + '\n')
    project_file = HERE / f'{PROJECT}.kicad_pro'
    if not project_file.exists():
        project = json.loads((Path(kicad_env.share_dir()) / 'template/kicad.kicad_pro').read_text())
        project.setdefault('meta', {})['filename'] = project_file.name
        project_file.write_text(json.dumps(project, indent=2) + '\n')
    for kind, extension, folder in [('sym', 'kicad_sym', 'lib'), ('fp', 'pretty', 'lib')]:
        table = f'{kind}_lib_table'
        # Project library assets are deliberately shared, circuit definitions are not.
        (HERE / f'{kind}-lib-table').write_text(
            f'({table}\n (version 7)\n (lib (name "eswitch")(type "KiCad")'
            f'(uri "${{KIPRJMOD}}/{folder}/eswitch.{extension}")(options "")(descr "Project symbol/footprint assets"))\n)\n')
    # Export the new GPIO map without relying on the old board's pin allocation.
    pinmap = [dict(channel=n, adc_gpio=a[1], in_gpio=i[1], den_gpio=d[1],
                   adc_module_pad=a[0], in_module_pad=i[0], den_module_pad=d[0])
              for n, (a, i, d) in enumerate(zip(circuit.ADC, circuit.CONTROL, circuit.DIAG), 1)]
    (HERE / 'pin-map.json').write_text(json.dumps(pinmap, indent=2) + '\n')


def bom():
    parts = {}
    for part in circuit.build():
        if 'MPN' not in part.fields:
            continue
        mpn = part.fields['MPN']
        row = parts.setdefault(mpn, dict(mpn=mpn, quantity=0, references=[]))
        row['quantity'] += int(part.fields.get('Quantity', 1))
        row['references'].append(part.ref)
        if 'HardwareMPN' in part.fields:
            hardware = part.fields['HardwareMPN']
            row = parts.setdefault(hardware, dict(mpn=hardware, quantity=0, references=[]))
            row['quantity'] += int(part.fields['HardwareQuantity'])
            row['references'].append(part.ref + ' mounting terminals')
        if 'ClipMPN' in part.fields:
            hardware = part.fields['ClipMPN']
            row = parts.setdefault(hardware, dict(mpn=hardware, quantity=0, references=[]))
            row['quantity'] += int(part.fields['ClipQuantity'])
            row['references'].append(part.ref + ' spring clips')
    for rating, qty in ((5, 5), (10, 2), (20, 1)):
        mpn = f'02870{rating:02}.PXCN'
        parts[mpn] = dict(mpn=mpn, quantity=qty, references=[f'{rating} A fuse inserts'])
    audit = json.loads((ROOT / 'docs/digikey-prices.json').read_text())
    prices = {p['mpn']: p for p in audit['parts']}
    money = lambda x: x.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    result = []
    for mpn, row in sorted(parts.items()):
        price = prices.get(mpn)
        item = dict(row, references=', '.join(row['references']))
        for boards in (1, 3):
            if price is None:
                item[f'exact_{boards}_board_usd'] = None
                continue
            n = row['quantity'] * boards
            t = max((p for p in price['price_breaks'] if p['quantity'] <= n), key=lambda p: p['quantity'])
            item[f'exact_{boards}_board_usd'] = float(money(Decimal(str(t['usd'])) * n))
        result.append(item)
    estimate = dict(status='PROVISIONAL_COMPONENT_SUBTOTAL_NOT_ORDER_BOM',
                    price_observation_date=audit['retrieved_utc_date'],
                    exclusions=['PCB', 'enclosure and F10 screws/washers/shims', 'assembly', 'shipping/taxes',
                                'unpriced BOM lines'],
                    fresh_stock_checked=False, lines=result,
                    one_board_usd=float(sum(Decimal(str(r['exact_1_board_usd'] or 0)) for r in result)),
                    three_board_usd=float(sum(Decimal(str(r['exact_3_board_usd'] or 0)) for r in result)),
                    unpriced=[r['mpn'] for r in result if r['exact_1_board_usd'] is None])
    (HERE / 'cost-estimate.json').write_text(json.dumps(estimate, indent=2) + '\n')
    with (HERE / 'bom-draft.csv').open('w', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['Quantity per board', 'MPN', 'References'])
        writer.writerows((r['quantity'], r['mpn'], r['references']) for r in result)
    print(f"Draft components: ${estimate['one_board_usd']:.2f} one board; "
          f"${estimate['three_board_usd'] / 3:.2f}/board in a three-board batch; "
          f"unpriced: {estimate['unpriced']}")


if __name__ == '__main__':
    schematic()
    bom()
