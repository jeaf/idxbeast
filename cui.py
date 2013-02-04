import ctypes
import msvcrt
import sys
import win32console

class COORD(ctypes.Structure):
  _fields_ = [("x", ctypes.c_short),
              ("y", ctypes.c_short)]

class SMALL_RECT(ctypes.Structure):
  _fields_ = [("left"  , ctypes.c_short),
              ("top"   , ctypes.c_short),
              ("right" , ctypes.c_short),
              ("bottom", ctypes.c_short)]

class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
  _fields_ = [("dwSize"             , COORD),
              ("dwCursorPosition"   , COORD), 
              ("wAttributes"        , ctypes.c_ushort), 
              ("srWindow"           , SMALL_RECT), 
              ("dwMaximumWindowSize", COORD)]

k32 = ctypes.windll.kernel32
stdout = k32.GetStdHandle(-11)

def wait_key():
  """
  Waits until a key is pressed. Returns the key.
  """
  while True:
    if msvcrt.kbhit():
      return msvcrt.getch()
    else:
      time.sleep(0.01)

def getcurpos():
  """
  Returns the cursor position as a COORD.
  """
  conInfo = CONSOLE_SCREEN_BUFFER_INFO()
  k32.GetConsoleScreenBufferInfo(stdout, ctypes.byref(conInfo)) 
  return conInfo.dwCursorPosition

def setcurpos(x, y):
  """
  Sets the cursor position.
  """
  k32.SetConsoleCursorPosition(stdout, COORD(x, y))

def putchxy(x, y, ch):
  """
  Puts a char at the specified position. The cursor position is not affected.
  """
  prevCurPos = getcurpos()
  setcurpos(x, y)
  msvcrt.putch(ch)
  setcurpos(prevCurPos.x, prevCurPos.y)

def get_console_size():
  """ Returns a (X, Y) tuple. """
  h = win32console.GetStdHandle(win32console.STD_OUTPUT_HANDLE)
  x = h.GetConsoleScreenBufferInfo()['MaximumWindowSize'].X
  y = h.GetConsoleScreenBufferInfo()['MaximumWindowSize'].Y
  return (x,y)

def set_text_color(colors=None):
  """
  Sets the text color on the console. Calling this function with None (the
  default) will restore default colors. The colors must be a iterable of
  strings.
  """

  flags = 0

  # If colors is None, use defaults colors
  if not colors:
    flags = win32console.FOREGROUND_BLUE | win32console.FOREGROUND_GREEN | win32console.FOREGROUND_RED

  # colors is set, process it
  else:

    # If colors is a single string, use this as the single flag
    if isinstance(colors, basestring):
      flags = win32console.__dict__[colors]

    # Otherwise, consider colors a list of strings
    else:
      for color in colors:
        flags = flags | win32console.__dict__[color]

  # Set the color
  h = win32console.GetStdHandle(win32console.STD_OUTPUT_HANDLE)
  h.SetConsoleTextAttribute(flags)

def write_color(text, colors, endline=False):
  """
  Prints the specified text, without endline, with the specified colors.
  After printing, the default color is restored.
  """
  text = unicode(text)
  set_text_color(colors)
  sys.stdout.write(text.encode('cp850'))
  if endline:
    sys.stdout.write('\n')
  set_text_color()

class Menu(object):
  """
  This class represents a command-line menu.
  """

  def __init__(self, callback=None):
    """
    Parameters:
      callback: a callable that will be called every time an item is selected.
                This callback won't be called if the item defines a specific
                callback.
    """

    self.callback = callback
    self.items    = list()

  def addItem(self, item):
    """
    Adds a new item to the menu.
    """

    self.items.append(item)
    if not item.callback:
      item.callback = self.callback
    return item

  def get_first_selected(self):
    """Returns the first selected items, None if none is selected."""
    for item in self.items:
      if item.selected:
        return item
    return None

  def show(self, sort=True):
    """
    Print menu items and wait for user input.
    Parameters:
      sort: if True, the menu items will be sorted by key. If False, the items
            will be displayed in the same order they were added.
    Returns:
      True when a valid item was selected, False if ESC was pressed.
    """

    # The list of available keys (used to generate a key when none has been
    # provided for a given item)
    availKeys = list('abcdefghijklmnopqrstuvwxyz')

    # Loop on all items to validate the type of items, organize by key
    itemsNoKey = []
    itemsByKey = dict()
    for item in self.items:
      if not isinstance(item, Item):
        raise Exception('Items composing the menu must be instances of the menu.Item class')
      if len(item.key) > 1:
        raise Exception('Item key cannot have more than one character')
      if item.key == '':
        itemsNoKey.append(item)
      else:
        if item.key in itemsByKey:
          raise Exception('Two items have the same key %s' % (item.key,))
        itemsByKey[item.key] = item
        availKeys.remove(item.key)

    # If some items have no key, generate a key for those
    for item in itemsNoKey:
      item.key = availKeys.pop(0)
      if item.key in itemsByKey:
        raise Exception('An auto generated key was already allocated')
      itemsByKey[item.key] = item

    # Print menu
    sortedItems = sorted(self.items) if sort else self.items
    for i, item in enumerate(sortedItems):
      item.lineNumber = getcurpos().y
      print item.getLine()

    # Wait for user input and return result(s)
    result = True
    while True:
      c = wait_key()
      if c in itemsByKey:
        if itemsByKey[c].trigger():
          break
      elif ord(c) == 13: # ENTER key
        break
      elif ord(c) == 27: # ESC key
        result = False
        break

    # Return result
    return result

class Item(object):
  def __init__(self, text, key='', flag=' ', actions=' *', toggle=False, obj=None, callback=None):
    """
    Parameters:
      text    : the text to display on the menu
      key     : the key (a char) to trigger the menu item. If none is provided
                (empty string), a key will automatically be provided
      flag    : A one-char flag that will be displayed on the left of the
                menu item
      actions : the list of "actions" available for this item. When the item
                triggers, it will loop between the actions.
      toggle  : If True, the menu item is allowed to toggle between all its
                actions when triggered. If False, a trigger will "commit"
                the menu (no return required)
      obj     : optional user-defined object to attach to the menu item
      callback: A callable to call when this item is selected. Overrides the
                callback defined on the menu itself, if any.
    """

    self.text     = text
    self.key      = key
    self.flag     = flag
    self.actions  = actions
    self.toggle   = toggle
    self.obj      = obj
    self.callback = callback
    self.selected = False # This will be set to True if trigger is
                          # called at least once.
  def __cmp__(self, other):
    if self.key < other.key:
      return -1
    if self.key == other.key:
      return 0
    return 1
  def __str__(self):
    strVal = self.key + ') ' + self.text
    if self.selected:
      strVal = strVal + ' (selected)'
    strVal = strVal + ' (action=' + self.actions[0] + ')'
    return strVal
  def __repr__(self):
    return '<menu.Item ' + self.key + ' ' + self.text + '>'
  def trigger(self):
    self.selected = True
    if self.callback:
      self.callback(self)
    self.actions = self.actions[1:] + self.actions[0]
    cio.putchxy(4, self.lineNumber, self.actions[0])
    return False if self.toggle else True
  def getLine(self):
    line = ' ' + self.flag + ' '
    line = line + '[' + self.actions[0] + '] '
    line = line + self.key + ') ' + self.text
    return line
