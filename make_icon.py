"""Generate a simple original icon locally; build-time Pillow only."""
from pathlib import Path
from PIL import Image, ImageDraw

folder=Path(__file__).parent/'assets'
folder.mkdir(exist_ok=True)
image=Image.new('RGBA',(256,256),(0,0,0,0))
draw=ImageDraw.Draw(image)
draw.rounded_rectangle((4,4,252,252),radius=66,fill='#397358')
draw.arc((44,44,212,212),start=280,end=615,fill='#D9E9D6',width=12)
draw.line([(128,78),(128,130),(164,150)],fill='white',width=12,joint='curve')
draw.ellipse((118,120,138,140),fill='white')
image.save(folder/'focus.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
