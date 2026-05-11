"""IM service operator CLI (feat-340-M1 R6).

This package exposes a single entrypoint (``python -m IM.cli init_admin``) so an
operator can seed the first authenticated user on a fresh deployment without
hitting the HTTP API. Once the admin user exists, additional users self-register
through ``POST /im/v1/auth/register``.
"""
