import runpy, sys
import cv2, torch
script=sys.argv.pop(1)
sys.argv[0]=script
torch.set_num_threads(4)
cv2.setNumThreads(1)
runpy.run_path(script,run_name='__main__')
