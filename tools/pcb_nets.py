"""Keep native KiCad net names/fields while accepting short generator aliases."""
import pcbnew
from sexp import parse_one, find, find_all


def short_name(item):
    name = item if isinstance(item, str) else item.GetNetname()
    return name.removeprefix("/")


def find_net(board, name):
    return board.FindNet(name) or board.FindNet("/" + name)


def sync_metadata(board, netlist_path):
    doc = parse_one(open(netlist_path).read())
    names = [find(net, "name")[1] for net in find_all(find(doc, "nets"), "net")]
    aliases = {short_name(name): name for name in names}
    assert len(aliases) == len(names), "Ambiguous net alias; hierarchical nets need explicit names"
    # Preserve every net code, pad assignment, track and zone. Only names change.
    for net in list(board.GetNetsByName().values()):
        alias = short_name(net)
        if alias in aliases:
            net.SetNetname(aliases[alias])
    # KiCad exports synthetic one-pin nets for explicit schematic NC flags, but
    # native PCB parity expects those physical pads to have no assigned net.
    unused = {net.GetNetCode() for net in board.GetNetsByName().values()
              if short_name(net).startswith("unconnected-")}
    assert not any(item.GetNetCode() in unused for item in board.GetTracks()), "Copper on an NC net"
    assert not any(zone.GetNetCode() in unused for zone in board.Zones()), "Zone on an NC net"
    components = {find(c, "ref")[1]: c for c in find_all(find(doc, "components"), "comp")}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() in unused:
                pad.SetNetCode(0)
        comp = components[fp.GetReference()]
        fp.SetValue(find(comp, "value")[1])
        fp.SetFPID(pcbnew.LIB_ID(*find(comp, "footprint")[1].split(":", 1)))
        for field in find_all(find(comp, "fields"), "field"):
            name = find(field, "name")[1]
            if name in ("Reference", "Value", "Footprint"):
                continue
            value = field[2] if len(field) > 2 else ""
            fp.SetField(name, value)
            item = fp.GetField(name)
            item.SetVisible(False)
            item.SetLayer(pcbnew.B_Fab if fp.GetLayer() == pcbnew.B_Cu else pcbnew.F_Fab)
            item.SetMirrored(fp.GetLayer() == pcbnew.B_Cu)
        path = pcbnew.KIID_PATH()
        path.push_back(pcbnew.KIID(find(comp, "tstamps")[1]))
        fp.SetPath(path)
        fp.SetExcludedFromBOM(fp.GetReference().startswith(("H", "NT", "TP")))
