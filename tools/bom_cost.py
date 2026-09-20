#!/usr/bin/env python3
"""Cost the exact one-board BOM using dated, packaging-specific observations."""
import csv
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
from manual_bom import rows

ROOT=Path(__file__).resolve().parent.parent

def money(x):
    return x.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

def main():
    audit=json.loads((ROOT/'docs/digikey-prices.json').read_text())
    prices={p['mpn']:p for p in audit['parts']}
    detail=[]
    for item in rows():
        p=prices[item['mpn']]
        assert 0 <= (date.today()-date.fromisoformat(p['checked'])).days <= 1, p['mpn']
        quantity=item['per_board']
        tiers=sorted(p['price_breaks'],key=lambda x:x['quantity'])
        tier=max((t for t in tiers if t['quantity']<=quantity),key=lambda x:x['quantity'])
        assert tier['packaging'] in ('Cut Tape (CT)','Bulk','Bag','Tray','Tube'),tier
        exact=money(Decimal(str(tier['usd']))*quantity)
        choices=[(exact,quantity,tier)]+[(money(Decimal(str(t['usd']))*t['quantity']),t['quantity'],t)
                 for t in tiers if quantity<t['quantity']<=p['stock']]
        cash,buy,buy_tier=min(choices,key=lambda x:(x[0],x[1]))
        detail.append(dict(mpn=p['mpn'],quantity=quantity,references=item['references'],
             assembly=item['assembly'],unit_usd=tier['usd'],line_usd=float(exact),
             economical_purchase_quantity=buy,purchase_unit_usd=buy_tier['usd'],
             purchase_line_usd=float(cash),spares=buy-quantity,url=p['url'],checked=p['checked']))
    total=sum(Decimal(str(p['line_usd'])) for p in detail)
    hardware=sum(Decimal(str(p['line_usd'])) for p in detail if p['assembly']=='Hardware')
    cash=sum(Decimal(str(p['purchase_line_usd'])) for p in detail)
    batch=[]
    for item in rows():
        p=prices[item['mpn']];quantity=3*item['per_board']
        assert p['stock']>=quantity,p['mpn']
        tier=max((t for t in p['price_breaks'] if t['quantity']<=quantity),key=lambda x:x['quantity'])
        batch.append(dict(mpn=p['mpn'],boards=3,quantity=quantity,unit_usd=tier['usd'],
                          line_usd=float(money(Decimal(str(tier['usd']))*quantity))))
    batch_total=sum(Decimal(str(p['line_usd'])) for p in batch)
    out=ROOT/'fab/digikey';out.mkdir(exist_ok=True)
    with (out/'cost-per-board.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(detail[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(detail)
    with (out/'economical-one-board-cart.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n')
        w.writerow(['Quantity','Manufacturer Part Number','Customer Reference'])
        for p in detail:w.writerow([p['economical_purchase_quantity'],p['mpn'],p['references']])
    with (out/'cost-three-board-build.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(batch[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(batch)
    result=dict(currency='USD',priced_date=audit['retrieved_utc_date'],boards=1,
        exact_quantity_bom_usd=float(total),fuses_and_standoffs_usd=float(hardware),
        board_components_usd=float(total-hardware),economical_cart_including_spares_usd=float(cash),
        three_board_build_usd=float(batch_total),three_board_build_per_unit_usd=float(money(batch_total/3)),
        exclusions=['bare PCB','assembly labor','solder/paste','enclosure-specific screws and washers',
                    'shipping','tax','tariffs'],parts=detail)
    (out/'cost-per-board.json').write_text(json.dumps(result,indent=2)+'\n')
    (ROOT/'docs/bom-cost.md').write_text(f'''# Revision C BOM cost — {audit['retrieved_utc_date']}

The current one-board BOM is **US${total:.2f}**, including the eight output fuse
inserts and twelve M3 standoffs. Board components account for ${total-hardware:.2f};
fuse inserts and standoffs account for ${hardware:.2f}.

Buying a few additional pieces to reach cheaper price breaks reduces the
one-board purchasing subtotal to **${cash:.2f}**, including those spares.
The installed BOM quantities remain for exactly one board.

For the planned **three-board build**, buying exactly three sets together costs
**${batch_total:.2f} total**, or **${money(batch_total/3):.2f} per board**, using the
applicable quantity breaks. This comparison does not change the one-board import
BOM. See the [three-board cost breakdown](../fab/digikey/cost-three-board-build.csv).

- [Exact one-board BOM](../fab/digikey/eswitch-digikey-bom.csv)
- [Price and quantity breakdown](../fab/digikey/cost-per-board.csv)
- [Optional cheaper cart, including explicitly listed spares](../fab/digikey/economical-one-board-cart.csv)
- [Dated price observations with individual DigiKey product links](digikey-prices.json)

These are displayed US distributor prices retrieved on the date above, with
cut tape or bulk packaging and price breaks applied to each line. They are an
estimate, not a reserved quote. PCB fabrication, assembly, solder/paste,
enclosure-specific screws and washers, shipping, taxes and tariffs are excluded.
See [release status](release-status.json) for fabrication readiness.
''')
    print(f'One-board exact BOM: ${total:.2f}; optional cart with spares: ${cash:.2f}')

if __name__=='__main__': main()
