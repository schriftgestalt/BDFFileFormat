# encoding: utf-8

###########################################################################################################
#
#
#	File Format Plugin
#	Implementation for exporting fonts through the Export dialog
#
#	Read the docs:
#	https://github.com/schriftgestalt/GlyphsSDK/tree/master/Python%20Templates/File%20Format
#
#	For help on the use of Interface Builder:
#	https://github.com/schriftgestalt/GlyphsSDK/tree/master/Python%20Templates
#
#
###########################################################################################################


from GlyphsApp.plugins import *
import os, traceback, math

from LaunchServices import LSCopyDefaultRoleHandlerForContentType, LSSetDefaultRoleHandlerForContentType, kLSRolesEditor
class BDFFileFormat(FileFormatPlugin):
	
	# Definitions of IBOutlets
	
	# The NSView object from the User Interface. Keep this here!
	dialog = objc.IBOutlet()
	
	# Example variables. You may delete them
	feedbackTextField = objc.IBOutlet()
	unicodeCheckBox = objc.IBOutlet()
	glyphWidthCheckbox = objc.IBOutlet()
	
	def settings(self):
		self.name = "BDF"
		self.icon = 'ExportIcon'
		self.toolbarPosition = 200
		
		# Load .nib dialog (with .extension)
		self.loadNib('IBdialog', __file__)
	
	def start(self):
		Command = "/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister";
		appPath = pathForResource("BDFApp", "app", __file__)
		Command += " \""+appPath+"\""
		os.system(Command)
		
		handler = LSCopyDefaultRoleHandlerForContentType(CFSTR("org.x.bdf"), kLSRolesEditor);
		if not handler or CFStringCompare(handler, CFSTR("com.georgseifert.glyphs2"), 0):
			LSSetDefaultRoleHandlerForContentType(CFSTR("org.x.bdf"), kLSRolesEditor, CFSTR("com.georgseifert.glyphs2"))
		
		if handler:
			CFRelease(handler)
	
	def export(self, font, filepath = None):
		
		if filepath is None:
			# Ask for export destination and write the file:
			title = "Choose export destination"
			proposedFilename = font.familyName
			fileTypes = ['bdf']
			# Call dialog
			filepath = GetSaveFile(title, proposedFilename, fileTypes)
		
		self.preExport(font)
		
		with open(filepath, "w") as f:
			self.writeFontInfo(font, f)
			self.writeGlyphs(font, f)
			f.write("ENDFONT")
		return True, None
	
	def preExport(self, font):
		self.size = round(font.upm / 10.0)
		master = font.masters[0]
		self.ascender = round(master.ascender / 10.0)
		self.descender = round(master.descender / 10.0)
		
		minX = 0
		minY = self.descender
		maxX = self.size
		maxY = self.size + self.descender
		gcount = 0
		for g in font.glyphs:
			if not g.export:
				continue
			l = g.layers[0]
			bounds = l.bounds
			minX = min(minX, NSMinX(bounds) / 10.0)
			minY = min(minY, NSMinY(bounds) / 10.0)
			maxX = max(maxX, NSMaxX(bounds) / 10.0)
			maxY = max(maxY, NSMaxY(bounds) / 10.0)
			gcount += 1
		
		self.originX = minX
		self.originY = minY
		self.width = maxX - minX
		self.height = maxY - minY
		self.count = gcount
		
	def writeFontInfo(self, font, f):
		f.write("STARTFONT 2.1\n")
		f.write("FONT %s\n" % font.familyName)
		f.write("SIZE %d 75 75\n" % self.size)
		f.write("FONTBOUNDINGBOX %d %d %d %d\n" % (self.width, self.height, self.originX, self.originY))
		f.write("STARTPROPERTIES 2\n")
		f.write("FONT_ASCENT %d\n" % self.ascender)
		f.write("FONT_DESCENT %d\n" % abs(self.descender))
		f.write("ENDPROPERTIES\n")
	
	def writeBitmap(self, layer, originX, originY, width, height, f):
		pixels = list()
		columns = int(math.ceil(width / 8.0) * 8)
		for y in range(height):
			row = list()
			for x in range(columns):
				row.append(False)
			pixels.append(row)
		for c in layer.components:
			if c.componentName == "pixel":
				pos = c.position
				row = int(height - round(pos.y / 10.0) + originY) - 1
				column = int(round(pos.x / 10.0) - originX)
				pixels[row][column] = True
		f.write("BITMAP\n")
		for row in pixels:
			pin = 1
			bits = 0
			for column in row:
				if column:
					bits = bits | pin
				bits = bits << 1
			bits = bits >> 1
			f.write("%02X\n" % bits)
		
	def writeGlyph(self, glyph, f):
		layer = glyph.layers[0]
		
		f.write("STARTCHAR %s\n" % glyph.name)
		if len(glyph.unicode) >=4:
			enc = int(glyph.unicode, 16)
			f.write("ENCODING %d\n" % enc)
		f.write("SWIDTH %d 0\n" % (100.0 * layer.width / self.size))
		f.write("DWIDTH %d 0\n" % round(layer.width / 10.0))
		
		minX = 0
		minY = self.descender
		maxX = round(layer.width / 10)
		maxY = self.size + self.descender
		bounds = layer.bounds
		minX = min(minX, NSMinX(bounds) / 10.0)
		minY = min(minY, NSMinY(bounds) / 10.0)
		maxX = max(maxX, NSMaxX(bounds) / 10.0)
		maxY = max(maxY, NSMaxY(bounds) / 10.0)
		originX = int(minX)
		originY = int(minY)
		width = int(maxX - minX)
		height = int(maxY - minY)
		f.write("BBX %d %d %d %d\n" % (width, height, originX, originY))
		self.writeBitmap(layer, originX, originY, width, height, f)
		f.write("ENDCHAR\n")
	
	def writeGlyphs(self, font, file):
		file.write("CHARS %d\n" % self.count)
		for g in font.glyphs:
			if not g.export:
				continue
			self.writeGlyph(g, file)
		
	
	def readFontInfo(self, font, file):
		for line in file:
			if line.startswith("ENDPROPERTIES"):
				return
			if line.startswith("FONT "):
				font.familyName = line[5:-1]
			elif line.startswith("SIZE "):
				self.size = int(line.split(" ")[1])
				font.upm = self.size * 10
				font.grid = 10
			elif line.startswith("FONT_ASCENT "):
				self.ascender = int(line.split(" ")[1])
				master = font.masters[0]
				master.ascender = self.ascender * 10
				master.capHeight = (self.ascender - 1) * 10
				master.xHeight = round(self.ascender * 0.66) * 10
			elif line.startswith("FONT_DESCENT "):
				self.descender = int(line.split(" ")[1])
				master = font.masters[0]
				master.descender = - self.descender * 10
	
	def drawPixel(self, font):
		pixel = GSGlyph()
		pixel.name = "pixel"
		pixel.export = False
		font.glyphs.append(pixel)
		layer = pixel.layers[0]
		layer.width = 10
		path = GSPath()
		
		Node = GSNode(NSPoint(10, 0), LINE)
		path.nodes.append(Node)
		Node = GSNode(NSPoint(10, 10), LINE)
		path.nodes.append(Node)
		Node = GSNode(NSPoint(0, 10), LINE)
		path.nodes.append(Node)
		Node = GSNode(NSPoint(0, 0), LINE)
		path.nodes.append(Node)
		
		path.closed = True
		layer.paths.append(path)
	
	def readBitmap(self, layer, originX, originY, width, height, file):
		row = 0
		columns = math.ceil(width / 8.0)
		highesBit = 0x80
		if columns > 1:
			highesBit = highesBit << 8
		if columns > 2:
			highesBit = highesBit << 8
		layer.setDisableUpdates()
		for line in file:
			bit = int(line, 16)
			for column in range(width):
				if (bit & highesBit) == highesBit:
					pixel = GSComponent("pixel")
					pixel.position = NSPoint((originX + column) * 10, (height - row + originY - 1) * 10)
					layer.addComponentFast_(pixel)
				bit = bit << 1
			row += 1
			if row >= height:
				break
		layer.enableFutureUpdates()
	
	def readGlyph(self, glyph, master, file):
		layer = GSLayer()
		glyph.layers[master.id] = layer
		originX = 0
		originY = self.descender
		width = self.size
		height = self.size
		for line in file:
			if line.startswith("ENDCHAR"):
				break
			elif line.startswith("ENCODING"):
				enc = int(line[9:-1])
				uni = "%04X" % enc
				glyph.unicode = uni
			elif line.startswith("DWIDTH"):
				width = int(line.split(" ")[1])
				layer.width = width * 10
			elif line.startswith("BBX"):
				elements = line.split(" ")
				originX = int(elements[3])
				originY = int(elements[4])
				width = int(elements[1])
				height = int(elements[2])
			elif line.startswith("BITMAP"):
				self.readBitmap(layer, originX, originY, width, height, file)
				break
	
	def readGlyphs(self, font, file):
		glyphs = []
		master = font.masters[0]
		for line in file:
			if line.startswith("ENDFONT"):
				break
			if line.startswith("STARTCHAR "):
				glyph = GSGlyph()
				glyph.undoManager().disableUndoRegistration()
				name = line[10:-1]
				# if name.startswith("U+"):
				# 	name = "uni"+name[2:]
				glyph.name = name
				glyphs.append(glyph)
				glyph.parent = font
				self.readGlyph(glyph, master, file)
				glyph.undoManager().enableUndoRegistration()
		font.glyphs.extend(glyphs)
		self.drawPixel(font)
	
	def read(self, filepath, fileType):
		font = GSFont()
		font.disableUpdateInterface()
		try:
			with open(filepath) as f:
				self.readFontInfo(font, f)
				self.readGlyphs(font, f)
		except:
			print traceback.format_exc()
		font.enableUpdateInterface()
		return font
	
	
	def __file__(self):
		"""Please leave this method unchanged"""
		return __file__
