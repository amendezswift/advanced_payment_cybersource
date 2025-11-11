# CyberSource Payment Gateway (Modernized)

## Descripción general
Este repositorio contiene el módulo **`payment_cybersource_modern`**, una integración limpia y modernizada del proveedor de pagos CyberSource para Odoo 17. El módulo mantiene la lógica funcional del desarrollo original, pero reestructura el código y las vistas para alinearse con los estándares actuales de Odoo.

## Comparativa con el módulo original
- **Organización y estructura**
  - Árbol de directorios simplificado centrado únicamente en los componentes necesarios del proveedor.
  - Nomenclatura consistente con las convenciones de Odoo (`models/`, `controllers/`, `data/`, `views/`, `static/`).
  - Hooks de instalación documentados directamente en `__init__.py`.
- **Vistas, etiquetas y componentes visuales**
  - Formulario inline diseñado con clases semánticas y etiquetas accesibles.
  - Campos de credenciales agrupados dentro de la sección nativa de configuración de proveedores.
  - Eliminación de vistas superfluas y recursos estáticos que no aportaban funcionalidad.
- **Refactorizaciones en Python y JS**
  - Controlador reorganizado en métodos privados reutilizables con validaciones claras y manejo de errores traducibles.
  - Modelos adaptados a decoradores modernos y documentación concisa.
  - JavaScript migrado a `patch` de Owl para extender `PaymentForm`, reemplazando la herencia basada en `include`.
- **Elementos eliminados o sustituidos**
  - Recursos promocionales y extensiones de POS ajenas al flujo de pago en sitio web.
  - Dependencias visuales redundantes y rutas con nombres genéricos, sustituidos por nomenclatura clara (`/payment/cybersource/process`).

## Instalación y actualización en Odoo 17
1. Copia la carpeta `payment_cybersource_modern` en tu directorio de addons.
2. Instala el paquete `cybersource-rest-client-python` en el entorno de Odoo.
3. Actualiza la lista de aplicaciones y localiza **CyberSource Payment Gateway (Modernized)**.
4. Instala o actualiza el módulo desde el panel de Apps.
5. Configura tus credenciales (Merchant ID, Key ID y Shared Secret) en **Contabilidad → Configuración → Métodos de Pago → Proveedores**.

Para actualizar desde el módulo original basta con desinstalar el addon anterior y sustituirlo por esta versión; los identificadores XML se mantuvieron compatibles para evitar recrear transacciones o métodos.

## Dependencias
- Módulos de Odoo: `payment`, `website_sale`.
- Dependencia externa de Python: `cybersource-rest-client-python`.

