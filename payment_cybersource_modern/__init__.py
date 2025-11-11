"""Initialization for the CyberSource payment provider module."""

from odoo.addons.payment import reset_payment_provider, setup_provider

from . import controllers  # noqa: F401  pylint: disable=unused-import
from . import models  # noqa: F401  pylint: disable=unused-import


def post_init_hook(env):
    """Register the CyberSource provider upon module installation."""
    setup_provider(env, "cybersource")


def uninstall_hook(env):
    """Remove the CyberSource provider configuration on uninstall."""
    reset_payment_provider(env, "cybersource")

