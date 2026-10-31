"""Linux child-only limits before exec; never called by ordinary core workflows."""
import os
import resource
import sys

# Runs in a fresh interpreter, avoiding preexec_fn in the threaded workbench.
resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024,) * 2)
resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024,) * 2)
resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
os.execv(sys.argv[1], sys.argv[1:])
