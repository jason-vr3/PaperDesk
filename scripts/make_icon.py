"""Geometric app icon; drawn locally without external assets."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1] / 'assets'
root.mkdir(exist_ok=True)
image = Image.new('RGBA', (256,256))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((8,8,248,248), radius=54, fill='#2478ed')
draw.rounded_rectangle((77,49,194,204), radius=14, fill='#9fc7ff')
draw.rounded_rectangle((59,37,176,192), radius=14, fill='white')
for y, right in ((87,146),(115,146),(143,126)):
    draw.rounded_rectangle((84,y,right,y+8), radius=4, fill='#2478ed')
image.save(root / 'PaperDesk.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
image.save(root / 'PaperDesk.png')
