"""Configuração SSL explícita para funcionar também no executável PyInstaller."""
import ssl

import certifi


def create_ssl_context():
    """Cria contexto TLS validando certificados com o bundle atualizado do certifi."""
    return ssl.create_default_context(cafile=certifi.where())
