# This file can be empty, or it can be used to signal that the 'core' directory is a package.
# By adding imports here, we can make them available at the package level.

# Import models to ensure they are registered with SQLAlchemy
from . import models  # noqa: F401
