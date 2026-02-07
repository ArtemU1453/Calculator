block_cipher=None

a=Analysis(
 ['main.py'],
 datas=[('app','app')],
 hiddenimports=['customtkinter']
)

exe=EXE(
 a.scripts,
 name="IndustrialCalculator",
 console=False
)
