import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.automation.password_finder import RadioPasswordFinder

finder = RadioPasswordFinder()
result = finder._try_login_robust('http://192.168.1.3', 'cednet', 'GCrouter@734', 'ZTE')
print('Robust check for wrong password (cednet / GCrouter@734) on 192.168.1.3:', result)
