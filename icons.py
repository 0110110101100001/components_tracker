"""Line icons of the PC components, one per panel row (24×24 SVG, drawn for this panel)."""

CPU = ('<rect x="6" y="6" width="12" height="12" rx="1.5"/>'
       '<rect x="9.5" y="9.5" width="5" height="5"/>'
       '<path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>')
RAM = ('<rect x="2" y="6" width="20" height="10" rx="1"/>'
       '<path d="M5.5 9.5h3v3h-3zM10.5 9.5h3v3h-3zM15.5 9.5h3v3h-3z"/>'
       '<path d="M4 16v3h7v-3M13 16v3h7v-3"/>')
GPU = ('<path d="M2 4h1v15"/>'
       '<rect x="3" y="6" width="19" height="11" rx="1"/>'
       '<circle cx="8.5" cy="11.5" r="3"/><circle cx="16.5" cy="11.5" r="3"/>'
       '<path d="M6 17v3h8v-3"/>')
BOLT = '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>'
DISK = ('<rect x="2" y="13" width="20" height="8" rx="2"/>'
        '<path d="M5.5 13 8 4h8l2.5 9M6 17h6M17 17h.01"/>')
NET = ('<rect x="3" y="3" width="18" height="18" rx="2"/>'
       '<path d="M7 16v-6h2V8h6v2h2v6zM10 16v-2M12 16v-2M14 16v-2"/>')

ICONS = {"cpu": CPU, "cores": CPU, "ram": RAM, "gpu": GPU, "vram": RAM, "gpu_power": BOLT,
         "disk": DISK, "disk_io": DISK, "net": NET}


def svg(name, colour):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{colour}" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round">{ICONS[name]}</svg>').encode()
