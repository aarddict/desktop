from __future__ import with_statement
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-i", "--input", dest="in_filename",
                  help="file containing full table of unicode collation keys")
parser.add_option("-o", "--output", dest="out_filename", 
                  help="output file with trimmed keys")

(options, args) = parser.parse_args()
print "Trimming", options.in_filename
filter = (
          'BOX DRAWINGS',
          'BRAILLE PATTERN', 
          'BYZANTINE MUSICAL SYMBOL', 
          'MUSICAL SYMBOL', 
          'COPTIC', 
          'ETHIOPIC', 
          'THAANA', 
          'ORIYA', 
          'TIBETAN', 
          'CHEROKEE',
          'OGHAM',
          'DESERET',
          'CANADIAN SYLLABICS',
          'MONGOLIAN',
          'GURMUKHI',
          'SINHALA',
          'KANNADA',
          'TELUGU',
          'LAO',
          'MYANMAR',
          'GUJARATI',
          'SYRIAC',
          'RUNIC'
          )

def is_filtered(line):
    for filtered in filter:
        if comment.startswith(filtered):
            return True

with open(options.in_filename, "r") as f:
    skip_count = 0
    with open(options.out_filename, "w") as output:
        for line in f:
            if line.startswith("#") or line.startswith("%"):
                continue
            if line.strip() == "":
                continue
            comment1_pos = line.find("#")
            comment2_pos = line.find("%")
            comment = ""
            if comment1_pos > -1:
                comment = line[comment1_pos+1:].strip()
            if comment2_pos > -1:
                comment = line[comment2_pos+1:].strip()
            
            if is_filtered(line):
                skip_count += 1
                continue                 
                
            line = line[:comment1_pos] + "\n"
            line = line[:comment2_pos] + "\n"
            line = line.strip() + "\n"
        
            if line.startswith("@"):
                pass
            else:
                output.write(line)

print "Output", options.out_filename+",", skip_count, "lines filtered"