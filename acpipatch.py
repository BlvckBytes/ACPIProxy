from util import hexbytes_to_ascii_name

class ACPIPatch:

  """
  Create a new ACPI-patch from find-hex-str-array, replace-hex-str-array
  and the original pattern
  """
  def __init__(self, finda, replacea, pattern):
    self.finds = ''.join(finda)
    self.findb = ''.join((map(lambda x: chr(int(x, 16)), finda))).encode('ascii')
    self.replaces = ''.join(replacea)
    self.replaceb = ''.join((map(lambda x: chr(int(x, 16)), replacea))).encode('ascii')
    self.pattern = pattern
    self.comment = f'SSDT-{pattern} {hexbytes_to_ascii_name(finda)} to {hexbytes_to_ascii_name(replacea)}'
  
  """
  Compare this instance against a given plist patch entry
  """
  def cmp(self, entry):
    return (
      entry.get('Comment') == self.comment and
      entry.get('Find') == self.findb and
      entry.get('Replace') == self.replaceb
    )

  """
  Find the plist patch entry corresponding to this instance
  or return None if it's not present
  """
  def find_entry(self, plist):
    # Iterate patches section
    patches = plist['ACPI']['Patch']
    for patch in patches:
      # Find matching entry
      if self.cmp(patch):
        return patch

    # Not found
    return None

  """
  Apply this patch to the plist if it's not yet present
  """
  def apply(self, plist):
    # Find entry in container list
    container = plist['ACPI']['Patch']
    entry = self.find_entry(plist)

    # Already existing, do nothing
    if entry != None:
      return

    # Create entry
    container.append({
      'Comment': self.comment,
      'Count': 0,
      'Limit': 0,
      'Skip': 0,
      'Enabled': True,
      'Find': self.findb,
      'Replace': self.replaceb
    })

  """
  Remove this patch from the plist if it's present
  """
  def undo(self, plist):
    # Find entry in container list
    container = plist['ACPI']['Patch']
    entry = self.find_entry(plist)

    # Remove entry by it's index from list if exists
    if entry != None:
      container.pop(container.index(entry))