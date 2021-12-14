import sys
import re
import os
import subprocess
from shutil import copy, which
from plistlib import load, dump

from acpipatch import ACPIPatch
from util import hexbytes_to_ascii_name

"""
Check that the required tool exists on the machine
"""
def tool_exists(name):
  return which(name) is not None

"""
Validate that all required files and folders exist within the
OC folder at the provided path
"""
def validate_oc_folder(path):
  # ACPI folder has to exist
  if not os.path.isdir(os.path.join(path, 'ACPI')):
    return False

  # config.plist has to exist
  if not os.path.exists(os.path.join(path, 'config.plist')):
    return False

  # Matches criteria
  return True

"""
Disassembles the provided AML and returns the file path
"""
def disassemble_acpi(path):
  # Create a carbon copy of this file to /tmp
  cc = copy(path, '/tmp')

  # Disassemble, result will also be saved in /tmp
  if subprocess.run(['iasl', '-da', cc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
    print('Could not disassemble the provided AML file!')
    sys.exit()

  # Return path of disassembled file
  return cc.rsplit('.', 1)[0] + '.dsl'

"""
Check whether or not this character is a valid
acpi name ascii character
"""
def is_valid_acpiname_char(dec_ascii):
  return (
    (dec_ascii >= 65 and dec_ascii <= 90) or # A-Z
    (dec_ascii >= 97 and dec_ascii <= 122) or # a-z
    (dec_ascii >= 48 and dec_ascii <= 57) or # 0-9
    (dec_ascii == 95) # _
  )

"""
Find all method declarations as byte-sequences within a
binary AML file according to this algorithm:

https://wiki.osdev.org/AML
Wait for 0x14 (MethodOp)

https://github.com/KevinOConnor/seabios/blob/master/src/fw/acpi.c (u8* encodeLen)
Shift next byte >> 6, this is the amount of length bytes, zero based
Collect those bytes

Then 4 bytes of method name
If a byte is a non-allowed char, reset to last char and try again
Finish method (push & reset)
"""
def find_method_declarations(dsdt):
  results = []

  buf = [] # Method byte-buffer
  numread = 0 # How many bytes left to read
  read_len = True # Whether or not reading length

  # Read file binary
  with open(dsdt, "rb") as aml:
    data = None
    while True:
      # Save previous pointer position for resets
      prevpos = aml.tell()
      data = aml.read(1).hex().upper()

      # EOF, file done
      if data == '':
        break

      # Parse hex to dec
      intrepr = int(data, 16)

      # Wait for a method to begin
      if len(buf) == 0 and data != '14':
        continue

      # Just read in opcode
      buf.append(data)
      if len(buf) == 1:
        continue

      # First byte after opcode, this dictates amount of length bytes
      if len(buf) == 2:
        # Figure out how many length bytes remain and set flag
        numread = intrepr >> 6
        read_len = numread > 0
        
        # No more length to read, directly jump to name
        if numread == 0:
          numread = 4
        continue

      # Not a valid acpi name char, re-set and search again
      if not read_len and not is_valid_acpiname_char(intrepr):
        buf = []
        aml.seek(prevpos)
        continue

      # Read remaining bytes
      if numread > 1:
        numread = numread - 1
        continue

      else:
        # Read name finished, finish method
        if not read_len:
          results.append(buf)
          buf = []
          continue

        # Read length finished, read in name
        numread = 4
        read_len = False
        continue

  return results

"""
+ => any number
! => any number or _
- => any letter
@ => any letter or _
? => any number or letter
* => any number or letter or _
"""
def translate_pattern_char(char):
  if char == '+':
    return '[0-9]'
  if char == '!':
    return '[0-9_]'
  if char == '-':
    return '[A-Z]'
  if char == '@':
    return '[A-Z_]'
  if char == '?':
    return '[A-Z0-9]'
  if char == '*':
    return '[A-Z0-9_]'
  return char

"""
Compile a custom made pattern into a regex ready to
be evaluated against strings
"""
def compile_custom_pattern(pattern):
  return re.compile(''.join([translate_pattern_char(x) for x in pattern]))

"""
Check if a single method declaration's name is
matching the provided name pattern
"""
def is_declaration_matching(declaration, pattern):
  name = hexbytes_to_ascii_name(declaration)
  return compile_custom_pattern(pattern).match(name)

"""
Filter a list of method declarations to only
keep declarations that match the name pattern
"""
def filter_declarations(declarations, pattern):
  return list(filter(lambda x: is_declaration_matching(x, pattern), declarations))

"""
Mark a byte-array containing an ACPI name
as patched by using an X at a zero-based index (0-3)
"""
def mark_patched(byte_arr, ind):
  res = byte_arr.copy()
  res[len(byte_arr) - 4 + ind] = '58' # ASCII X
  return res

"""
Check whether or not a list of resulting patches is unique
"""
def are_patches_unique(patches):
  strpatches = list(map(lambda y: ''.join(y), patches))
  return len(strpatches) == len(set(strpatches))

"""
Main entry point of the program
"""
def main(args):
  # Has to have three args
  if len(args) != 4:
    print('Usage: acpiproxy.py <apply/undo> <Pattern> <Path-To-OC-Folder> <Path-To-DSDT.aml>')
    sys.exit()

  # Destructure args into separate variables
  action, pattern, oc, dsdt = args

  # Action has to be valid
  if action != 'apply' and action != 'undo':
    print('Invalid action provided! Only use: apply,undo')
    sys.exit()

  # Pattern has to be valid
  if not re.compile('[A-Z0-9_+!\-@?*]{4}').match(pattern):
    print('Invalid pattern provided! Only use: A-Z,0-9,_,+,!,-,@,?,* exactly four times!')
    sys.exit()

  # OC has to be a valid OpenCore folder
  if not validate_oc_folder(oc):
    print('Please provide a valid OpenCore folder location!')
    sys.exit()

  # DSDT has to be a valid file
  if not os.path.exists(dsdt):
    print('Please provide a valid DSDT.aml!')
    sys.exit()

  # Make sure iasl is in $PATH
  if not tool_exists('iasl'):
    print('Please install "iasl" in your PATH!')
    sys.exit()

  # Find method declarations
  declarations = find_method_declarations(dsdt)

  # Filter based on input mask
  declarations = filter_declarations(declarations, pattern)

  # Try all possible indices to mark patching with an X
  # until unique accross all items
  patches = []
  for x_ind in range(0, 3):
    # Create case where all entries are patched at same index
    case = list(map(lambda x: mark_patched(x, x_ind), declarations))

    # If that's unique, save, try again otherwise
    if are_patches_unique(case):
      patches = case
      break

  # Convert to patch class instances
  patches = [ACPIPatch(declarations[x], patches[x], pattern) for x in range(0, len(declarations))]

  # Load plist, close file
  plist = None
  print('Reading plist...')
  with open(os.path.join(oc, 'config.plist'), 'rb') as plist_input:
    plist = load(plist_input)

  # Debug print
  for patch in patches:
    print(f'{"Applying" if action == "apply" else "Undoing"}: {patch.comment}: {patch.finds} -> {patch.replaces}')

    # Apply
    if action == 'apply':
      patch.apply(plist)
    # Undo
    else:
      patch.undo(plist)

  # Write plist, close file
  print('Writing plist...')
  with open(os.path.join(oc, 'config.plist'), 'wb') as plist_output:
    dump(plist, plist_output)

# Invoke main function with cli args
if __name__ == '__main__':
  main(sys.argv[1:])