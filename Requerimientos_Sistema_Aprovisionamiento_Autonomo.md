# **Documento de Requerimientos del Sistema (DRS)**

**Proyecto:** Sistema de Aprovisionamiento Autónomo basado en Machine Learning y Restricciones Presupuestales

# **1\. Resumen Ejecutivo**

El propósito de este proyecto es desarrollar e implementar un sistema de aprovisionamiento autónomo capaz de predecir la demanda de productos utilizando algoritmos de Machine Learning y generar órdenes de compra optimizadas que respeten las restricciones de presupuesto establecidas por la gerencia.

# **2\. Objetivos del Negocio**

* **Minimizar las roturas de stock** (*stockouts*) anticipando la demanda con precisión.  
* **Optimizar la asignación del capital de trabajo** (presupuesto) hacia los productos de mayor rotación y rentabilidad.  
* **Reducir el tiempo operativo manual** en el análisis y generación de órdenes de compra.

# **3\. Alcance del Proyecto**

* **Dentro del alcance:** Ingesta de datos históricos, modelado predictivo de demanda, motor de optimización matemática para restricciones de presupuesto y generación de la orden de compra propuesta mediante una API.  
* **Fuera del alcance:** Integración automática directa con software contable (ERP) y gestión física operativa de los almacenes.

# **4\. Requerimientos Funcionales (RF)**

| Código | Módulo | Descripción del Requerimiento |
| :---- | :---- | :---- |
| **RF01** | Gestión de Datos | El sistema debe permitir la carga y actualización de datos históricos de ventas, inventario actual, costos unitarios y tiempos de entrega (*lead times*). |
| **RF02** | Predicción de Demanda | El módulo de Machine Learning debe procesar el histórico y proyectar la demanda esperada por SKU (producto) para el próximo periodo (ej. próxima semana o mes). |
| **RF03** | Ingreso de Restricciones | La API o interfaz debe permitir al usuario ingresar el límite de presupuesto (capital) disponible para el ciclo de compra. |
| **RF04** | Optimización Presupuestal | El sistema debe ejecutar un modelo de investigación de operaciones (optimización tipo *Knapsack*) para priorizar las compras, maximizando el cumplimiento de la demanda proyectada sin exceder el presupuesto. |
| **RF05** | Generación de Recomendaciones | El sistema debe emitir un reporte final u orden de compra detallando: qué producto comprar, cantidad exacta, y la suma total de inversión proyectada. |

* **RF06 \- Módulo de Entrenamiento Continuo:** El sistema debe incorporar un pipeline (flujo) que permita el re-entrenamiento periódico del modelo de Machine Learning utilizando la nueva data histórica recolectada, asegurando que el modelo mantenga su precisión.

# **5\. Requerimientos No Funcionales (RNF)**

* **RNF01 \- Rendimiento:** El motor de inferencia y optimización debe generar la recomendación en un tiempo aceptable (idealmente menor a 30 segundos).  
* **RNF02 \- Escalabilidad:** La arquitectura debe estar modularizada como una API RESTful (ej. FastAPI o Flask) y preparada para ser desplegada en infraestructura Cloud (como Render o Railway).  
* **RNF03 \- Persistencia de Datos:** El modelo de datos estará alojado en una base de datos escalable (como MongoDB Atlas) para facilitar la lectura del catálogo e histórico.  
* **RNF04 \- Control de Versiones:** Todo el código, scripts de entrenamiento y estructuración matemática deberá estar documentado y versionado en GitHub.

## **5.1. Requerimientos de Seguridad de la Información (RNF-SEG)**

* **Gestión de Credenciales y Repositorios:** Ocultar API keys mediante variables de entorno, eliminación y prevención de secretos en el repositorio Git, y escaneo periódico de vulnerabilidades en dependencias.  
* **Seguridad de Base de Datos:** Conexión segura mediante Key pública/privada, parametrización estricta de consultas (queries) para evitar inyección SQL, e implementación de políticas de Row Level Security (RLS) para restringir el acceso a nivel de fila.  
* **Autenticación y Autorización:** Forzar la validación de autenticación del lado del servidor, almacenar contraseñas utilizando algoritmos de hashing fuertes, proteger las cookies de sesión (banderas HttpOnly y Secure), y restringir el acceso a los registros del sistema (logs).  
* **Protección de la API y Red:** Forzar todo el tráfico a través de HTTPS, agregar encabezados de seguridad (Security Headers como CORS, HSTS), implementar Rate Limiting para evitar abusos, integrar protección contra bots, y devolver strictly solo los datos necesarios en las respuestas de la API (evitar fuga de datos).  
* **Validación y Manejo de Datos:** Validar todos los inputs, sanitizar el contenido proveniente del usuario, bloquear la manipulación de campos no autorizados (Mass Assignment), encriptar los datos sensibles tanto en tránsito como en reposo, y restringir severamente los tipos y tamaños en la subida de archivos.

# **6\. Supuestos y Dependencias**

* Se cuenta con un conjunto de datos (*dataset*) histórico base lo suficientemente limpio para la fase de entrenamiento de los modelos predictivos.  
* Las variaciones de costo unitario por proveedor son predecibles o se mantienen estables a lo largo de cada ciclo de planeación.

