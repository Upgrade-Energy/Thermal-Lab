"""Conservative TC001 Max connection guidance from read-only Windows topology."""
import re


def usb_route(device):
    paths=device.get('location_paths') or []
    if isinstance(paths,str):paths=[paths]
    for path in paths:
        match=re.fullmatch(r'(PCIROOT\([^)]*\)(?:#PCI\([^)]*\))*#USBROOT\([^)]*\))((?:#USB\([^)]*\))+)',path.upper())
        if match:
            ports=re.findall(r'#USB\([^)]*\)',match[2])
            return match[1],ports
    return None


def connection_guidance(devices):
    healthy=[d for d in devices if d.get('problem_code')==0]
    if not healthy:return 'No healthy TC001 Max detected. Connect a camera, then Refresh.'
    if len(healthy)==1:return 'One camera detected. Refresh after connecting a second camera.'
    routes=[usb_route(d) for d in healthy]
    known=[r for r in routes if r is not None]
    for i,(controller,ports) in enumerate(known):
        for other_controller,other_ports in known[i+1:]:
            if controller==other_controller and ports[0]==other_ports[0] and len(ports)>1 and len(other_ports)>1:
                return 'SHARED HUB PATH: full-quality dual capture exceeds this USB 2 link. Move one camera to a separate USB controller; then Refresh.'
    if len(known)!=len(routes):return 'USB path unknown. Separate controller connections are recommended; verify both streams before recording.'
    if len({r[0] for r in known})==len(known):
        return 'Separate USB controllers detected. Verify both live streams before recording; full camera quality is preserved.'
    return 'Different root ports on a shared controller. Bandwidth is unverified; test both streams before recording.'
