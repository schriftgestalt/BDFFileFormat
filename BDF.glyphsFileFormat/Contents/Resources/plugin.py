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

from __future__ import print_function
from GlyphsApp import *
from GlyphsApp.plugins import *
from GlyphsApp.plugins import pathForResource
import os, traceback, math, objc
from CoreFoundation import CFSTR, CFStringCompare, CFRelease
from LaunchServices import LSCopyDefaultRoleHandlerForContentType, LSSetDefaultRoleHandlerForContentType, kLSRolesEditor

class BDFFileFormat(FileFormatPlugin):

	# Definitions of IBOutlets

	# The NSView object from the User Interface. Keep this here!
	dialog = objc.IBOutlet()

	# Example variables. You may delete them
	feedbackTextField = objc.IBOutlet()
	unicodeCheckBox = objc.IBOutlet()
	glyphWidthCheckbox = objc.IBOutlet()

	@objc.python_method
	def settings(self):
		self.name = "BDF"
		self.icon = 'ExportIcon'
		self.toolbarPosition = 200

		# Load .nib dialog (with .extension)
		self.loadNib('IBdialog', __file__)

	@objc.python_method
	def start(self):
		Command = "/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister";
		appPath = pathForResource("BDFApp", "app", __file__)
		Command += " \""+appPath+"\""
		os.system(Command)

		handler = LSCopyDefaultRoleHandlerForContentType(CFSTR("org.x.bdf"), kLSRolesEditor)
		identifier = NSBundle.mainBundle().bundleIdentifier()
		if not handler or CFStringCompare(handler, CFSTR(identifier), 0):
			LSSetDefaultRoleHandlerForContentType(CFSTR("org.x.bdf"), kLSRolesEditor, CFSTR(identifier))

		if handler:
			CFRelease(handler)

	@objc.python_method
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

	@objc.python_method
	def preExport(self, font):
		self.factor = font.grid
		self.size = round(font.upm / self.factor)
		master = font.masters[0]
		self.ascender = round(master.ascender / self.factor)
		self.descender = round(master.descender / self.factor)

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
			minX = min(minX, NSMinX(bounds) / self.factor)
			minY = min(minY, NSMinY(bounds) / self.factor)
			maxX = max(maxX, NSMaxX(bounds) / self.factor)
			maxY = max(maxY, NSMaxY(bounds) / self.factor)
			gcount += 1

		self.originX = minX
		self.originY = minY
		self.width = maxX - minX
		self.height = maxY - minY
		self.count = gcount

	@objc.python_method
	def writeFontInfo(self, font, f):

		self.resolution = 75
		if "BDFresultion" in font.customParameters:
			self.resolution = int(font.customParameters["BDFresultion"])
		self.pixel = "pixel"
		if "BDFpixel" in font.customParameters:
			self.pixel = font.customParameters["BDFpixel"]

		f.write("STARTFONT 2.1\n")
		f.write("FONT %s\n" % font.familyName)
		f.write("SIZE %d %d %d\n" % (self.size, self.resolution, self.resolution))
		f.write("FONTBOUNDINGBOX %d %d %d %d\n" % (self.width, self.height, self.originX, self.originY))
		f.write("STARTPROPERTIES 2\n")
		f.write("FONT_ASCENT %d\n" % self.ascender)
		f.write("FONT_DESCENT %d\n" % abs(self.descender))
		f.write("ENDPROPERTIES\n")

	@objc.python_method
	def writeBitmap(self, layer, originX, originY, width, height, f):
		pixels = list()
		columns = int(math.ceil(width / 8.0) * 8)
		for y in range(height):
			row = list()
			for x in range(columns):
				row.append(False)
			pixels.append(row)
		for c in layer.components:
			if c.componentName == self.pixel:
				pos = c.position
				row = int(height - round(pos.y / self.factor) + originY) - 1
				column = int(round(pos.x / self.factor) - originX)
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
			if columns > 48:
				f.write("%010X\n" % bits)
			if columns > 32:
				f.write("%08X\n" % bits)
			elif columns > 16:
				f.write("%06X\n" % bits)
			elif columns > 8:
				f.write("%04X\n" % bits)
			else:
				f.write("%02X\n" % bits)

	@objc.python_method
	def writeGlyph(self, glyph, f):
		layer = glyph.layers[0]

		f.write("STARTCHAR %s\n" % glyph.name)
		if glyph.unicode and len(glyph.unicode) >=4:
			enc = int(glyph.unicode, 16)
			f.write("ENCODING %d\n" % enc)
		f.write("SWIDTH %d 0\n" % ((75 / self.resolution) * 100.0 * layer.width / self.size))
		f.write("DWIDTH %d 0\n" % round(layer.width / self.factor))

		minX = 10000
		minY = 10000
		maxX = 0
		maxY = 0
		bounds = layer.bounds
		minX = min(minX, NSMinX(bounds) / self.factor)
		minY = min(minY, NSMinY(bounds) / self.factor)
		maxX = max(maxX, NSMaxX(bounds) / self.factor)
		maxY = max(maxY, NSMaxY(bounds) / self.factor)
		originX = int(minX)
		originY = int(minY)
		width = int(maxX - minX)
		height = int(maxY - minY)
		f.write("BBX %d %d %d %d\n" % (width, height, originX, originY))
		self.writeBitmap(layer, originX, originY, width, height, f)
		f.write("ENDCHAR\n")

	@objc.python_method
	def writeGlyphs(self, font, file):
		file.write("CHARS %d\n" % self.count)
		for g in font.glyphs:
			if not g.export:
				continue
			self.writeGlyph(g, file)

	@objc.python_method
	def readFontInfo(self, font, file):
		for line in file:
			if line.startswith("ENDPROPERTIES"):
				return
			if line.startswith("FONT "):
				font.familyName = line[5:-1]
			elif line.startswith("SIZE "):
				size = line.split(" ")
				self.size = int(size[1])
				font.upm = self.size * 10
				font.grid = 10

				resultion = int(size[2])
				if resultion != 75:
					font.customParameters["BDFresultion"] = resultion

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
			elif line.startswith("FAMILY_NAME "):
				if font.familyName != "new Font":
					font.customParameters["postscriptFontName"] = font.familyName
				font.familyName = line[12:-1].strip("\" ")
			elif line.startswith("FOUNDRY "):
				font.manufacturer = line[8:-1].strip("\" ")
			elif line.startswith("WEIGHT_NAME "):
				instance = font.instances[0]
				if instance is None:
					instance = GSInstance()
					font.instances.append(instance)
				instance.name = line[12:-1].strip("\" ")
			elif line.startswith("COPYRIGHT "):
				font.copyright = line[10:-1].strip("\" ")
			elif line.startswith("FONT_VERSION "):
				versionString = line[13:-1].strip("\" ")
				try:
					version = versionString.split(".")
					font.versionMajor = int(version[0])
					font.versionMinor = int(version[1])
				except:
					pass
			elif line.startswith("UNDERLINE_POSITION "):
				master = font.masters[0]
				master.customParameters["underlinePosition"] = int(line[19:-1]) * 10
			elif line.startswith("UNDERLINE_THICKNESS "):
				master = font.masters[0]
				master.customParameters["underlineThickness"] = int(line[20:-1]) * 10

	@objc.python_method
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

	@objc.python_method
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
					pixel.automaticAlignment = False
					layer.components.append(pixel)
				bit = bit << 1
			row += 1
			if row >= height:
				break
		layer.enableFutureUpdates()

	@objc.python_method
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

	@objc.python_method
	def readGlyphs(self, font, file):
		glyphs = []
		master = font.masters[0]
		niceNames = not Glyphs.boolDefaults["ImportKeepGlyphsNames"]
		for line in file:
			if line.startswith("ENDFONT"):
				break
			if line.startswith("STARTCHAR "):
				glyph = GSGlyph()
				glyph.undoManager().disableUndoRegistration()
				name = line[10:-1]
				if niceNames:
					if name.startswith("U+"):
						name = "uni"+name[2:]
					newName = Glyphs.niceGlyphName(name)
					if newName is not None:
						name = newName
				glyph.name = name

				glyphs.append(glyph)
				glyph.parent = font
				self.readGlyph(glyph, master, file)
				glyph.undoManager().enableUndoRegistration()
		font.glyphs.extend(glyphs)
		self.drawPixel(font)

	@objc.python_method
	def read(self, filepath, fileType):
		font = GSFont()
		font.disableUpdateInterface()
		with open(filepath) as f:
			self.readFontInfo(font, f)
			self.readGlyphs(font, f)
		font.enableUpdateInterface()
		return font

	@objc.python_method
	def __file__(self):
		"""Please leave this method unchanged"""
		return __file__
