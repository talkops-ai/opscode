"""DevOps Coder (opscode) agent package root."""

import logging

from opscode._debug import configure_debug_logging
from opscode._debug_buffer import install_log_buffer

__version__ = "0.1.0"

install_log_buffer(logging.getLogger(__name__))  # noqa: RUF067  # attach the always-on tail first so warnings from configure_debug_logging are captured
configure_debug_logging(logging.getLogger(__name__))  # noqa: RUF067  # package logger must be configured before child modules emit logs; sets the final level over the buffer's INFO floor
