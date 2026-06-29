import { CameraView, useCameraPermissions } from "expo-camera";
import { StatusBar } from "expo-status-bar";
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  Dimensions,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { CLASIFICAR_URL, DONACIONES_URL, RESUMEN_URL, SUBCATEGORIAS_URL } from "./config";

const { width } = Dimensions.get("window");

const CATEGORY_COLORS = {
  Ropa: "#6C63FF",
  Agua: "#00B4D8",
  Medicamentos: "#E63946",
  Alimentos: "#2DC653",
  Higiene: "#9B5DE5",
  Otros: "#F4A261",
  ropa: "#6C63FF",
  agua: "#00B4D8",
  medicamentos: "#E63946",
  comida: "#2DC653",
  higiene: "#9B5DE5",
  limpieza: "#118AB2",
  calzado: "#8338EC",
  otros: "#F4A261",
};

const PRIORITY_COLORS = {
  Alta: "#E63946",
  Media: "#F4A261",
  Baja: "#2DC653",
};

const CENTROS_ACOPIO = [
  "Centro principal",
  "Centro Norte",
  "Centro Sur",
  "Centro Este",
  "Centro Oeste",
  "Iglesia San José",
  "Escuela Bolívar",
  "Comedor comunitario",
];

const CATEGORIAS_EDITABLES = [
  { key: "comida", label: "Comida", icon: "🥫" },
  { key: "medicamentos", label: "Medicamentos", icon: "💊" },
  { key: "higiene", label: "Higiene", icon: "🧼" },
  { key: "limpieza", label: "Limpieza", icon: "🧴" },
  { key: "ropa", label: "Ropa", icon: "👕" },
  { key: "calzado", label: "Calzado", icon: "👟" },
  { key: "agua", label: "Agua", icon: "💧" },
  { key: "otros", label: "Otros", icon: "📦" },
];

const CATEGORY_ICONS = {
  Ropa: "👕",
  Agua: "💧",
  Medicamentos: "💊",
  Alimentos: "🥫",
  Higiene: "🧼",
  Otros: "📦",
  ropa: "👕",
  agua: "💧",
  medicamentos: "💊",
  comida: "🥫",
  higiene: "🧼",
  limpieza: "🧴",
  calzado: "👟",
  otros: "📦",
};

function SubcategoriaSelect({ categoria, subcategoria, onChange, onAdmin }) {
  const [abierto, setAbierto] = useState(false);
  const [opciones, setOpciones] = useState([]);
  const [modoOtro, setModoOtro] = useState(false);
  const [textoOtro, setTextoOtro] = useState("");

  useEffect(() => {
    let mounted = true;
    const cargar = async () => {
      try {
        const respuesta = await fetch(`${SUBCATEGORIAS_URL}?categoria=${encodeURIComponent(categoria)}`);
        const datos = await respuesta.json();
        if (mounted && respuesta.ok) setOpciones(datos);
      } catch (err) {
        console.warn("Error cargando subcategorías:", err.message);
      }
    };
    cargar();
    return () => { mounted = false; };
  }, [categoria]);

  useEffect(() => {
    const existe = opciones.some((o) => o.nombre.toLowerCase() === (subcategoria || "").toLowerCase());
    setModoOtro(!!subcategoria && !existe);
    setTextoOtro(subcategoria || "");
  }, [subcategoria, opciones]);

  const seleccionar = (nombre) => {
    onChange(nombre);
    setModoOtro(false);
    setAbierto(false);
  };

  return (
    <>
      <TouchableOpacity style={styles.selectBoton} onPress={() => setAbierto(true)}>
        <Text style={styles.selectTexto} numberOfLines={1}>
          {subcategoria || "Seleccionar subcategoría..."}
        </Text>
        <Text style={styles.selectFlecha}>▾</Text>
      </TouchableOpacity>

      {modoOtro && (
        <TextInput
          style={[styles.inputEditable, { marginTop: 8 }]}
          value={textoOtro}
          onChangeText={(texto) => {
            setTextoOtro(texto);
            onChange(texto);
          }}
          placeholder="Escribe el nombre del producto"
          maxLength={60}
        />
      )}

      <Modal visible={abierto} transparent animationType="fade" onRequestClose={() => setAbierto(false)}>
        <Pressable style={styles.selectFondo} onPress={() => setAbierto(false)}>
          <Pressable style={styles.selectTarjeta} onPress={() => {}}>
            <Text style={styles.selectTitulo}>Subcategorías de {categoria}</Text>
            <ScrollView showsVerticalScrollIndicator={false}>
              {opciones.length === 0 ? (
                <Text style={styles.textoVacio}>No hay subcategorías registradas.</Text>
              ) : (
                opciones.map((op) => {
                  const activa = subcategoria === op.nombre;
                  return (
                    <TouchableOpacity
                      key={op.id}
                      style={[styles.selectItem, activa && { backgroundColor: "#6C63FF18" }]}
                      onPress={() => seleccionar(op.nombre)}
                    >
                      <Text style={[styles.selectItemTexto, activa && { color: "#6C63FF", fontWeight: "800" }]}>{op.nombre}</Text>
                      {activa && <Text style={[styles.selectCheck, { color: "#6C63FF" }]}>✓</Text>}
                    </TouchableOpacity>
                  );
                })
              )}
              <TouchableOpacity style={[styles.selectItem, { borderTopWidth: 1, borderTopColor: "#E0E0E0", marginTop: 4 }]} onPress={() => { seleccionar(""); setModoOtro(true); setAbierto(false); }}>
                <Text style={[styles.selectItemTexto, { color: "#6C63FF" }]}>✏️ Otro (escribir)</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.selectItem} onPress={() => { setAbierto(false); onAdmin(); }}>
                <Text style={[styles.selectItemTexto, { color: "#118AB2" }]}>⚙️ Administrar categorías</Text>
              </TouchableOpacity>
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

function CentroSelect({ centro, onChange }) {
  const [abierto, setAbierto] = useState(false);

  return (
    <>
      <TouchableOpacity style={styles.selectBoton} onPress={() => setAbierto(true)}>
        <Text style={styles.selectTexto}>{centro}</Text>
        <Text style={styles.selectFlecha}>▾</Text>
      </TouchableOpacity>

      <Modal visible={abierto} transparent animationType="fade" onRequestClose={() => setAbierto(false)}>
        <Pressable style={styles.selectFondo} onPress={() => setAbierto(false)}>
          <Pressable style={styles.selectTarjeta} onPress={() => {}}>
            <Text style={styles.selectTitulo}>Centro de acopio</Text>
            <ScrollView showsVerticalScrollIndicator={false}>
              {CENTROS_ACOPIO.map((c) => {
                const activa = centro === c;
                return (
                  <TouchableOpacity
                    key={c}
                    style={[styles.selectItem, activa && { backgroundColor: "#6C63FF18" }]}
                    onPress={() => {
                      onChange(c);
                      setAbierto(false);
                    }}
                  >
                    <Text style={[styles.selectItemTexto, activa && { color: "#6C63FF", fontWeight: "800" }]}>{c}</Text>
                    {activa && <Text style={[styles.selectCheck, { color: "#6C63FF" }]}>✓</Text>}
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

function CategoriaSelect({ categoria, onChange }) {
  const [abierto, setAbierto] = useState(false);
  const seleccionada = CATEGORIAS_EDITABLES.find((c) => c.key === categoria) || CATEGORIAS_EDITABLES[CATEGORIAS_EDITABLES.length - 1];
  const color = CATEGORY_COLORS[categoria] || "#6C63FF";

  return (
    <>
      <TouchableOpacity style={[styles.selectBoton, { borderColor: color }]} onPress={() => setAbierto(true)}>
        <Text style={styles.selectIcono}>{seleccionada.icon}</Text>
        <Text style={styles.selectTexto}>{seleccionada.label}</Text>
        <Text style={styles.selectFlecha}>▾</Text>
      </TouchableOpacity>

      <Modal visible={abierto} transparent animationType="fade" onRequestClose={() => setAbierto(false)}>
        <Pressable style={styles.selectFondo} onPress={() => setAbierto(false)}>
          <Pressable style={styles.selectTarjeta} onPress={() => {}}>
            <Text style={styles.selectTitulo}>Seleccionar categoría</Text>
            <ScrollView showsVerticalScrollIndicator={false}>
              {CATEGORIAS_EDITABLES.map((cat) => {
                const activa = categoria === cat.key;
                const catColor = CATEGORY_COLORS[cat.key] || "#6C63FF";
                return (
                  <TouchableOpacity
                    key={cat.key}
                    style={[styles.selectItem, activa && { backgroundColor: catColor + "18" }]}
                    onPress={() => {
                      onChange(cat.key);
                      setAbierto(false);
                    }}
                  >
                    <Text style={styles.selectItemIcono}>{cat.icon}</Text>
                    <Text style={[styles.selectItemTexto, activa && { color: catColor, fontWeight: "800" }]}>{cat.label}</Text>
                    {activa && <Text style={[styles.selectCheck, { color: catColor }]}>✓</Text>}
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

export default function App() {
  const cameraRef = useRef(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [cargando, setCargando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [mensajeGuardado, setMensajeGuardado] = useState(null);
  const [inventarioVisible, setInventarioVisible] = useState(false);
  const [adminVisible, setAdminVisible] = useState(false);
  const [subcategorias, setSubcategorias] = useState([]);
  const [nuevaSubcategoria, setNuevaSubcategoria] = useState("");
  const [categoriaNuevaSub, setCategoriaNuevaSub] = useState(CATEGORIAS_EDITABLES[0].key);
  const [subcategoriaEditando, setSubcategoriaEditando] = useState(null);
  const [textoEditadoSub, setTextoEditadoSub] = useState("");
  const [donaciones, setDonaciones] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [centroAcopio, setCentroAcopio] = useState(CENTROS_ACOPIO[0]);
  const pulseAnim = useRef(new Animated.Value(1)).current;

  const iniciarPulso = () => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.15, duration: 600, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 600, useNativeDriver: true }),
      ])
    ).start();
  };

  const detenerPulso = () => {
    pulseAnim.stopAnimation();
    pulseAnim.setValue(1);
  };

  const capturarYClasificar = async () => {
    if (!cameraRef.current || cargando) return;
    try {
      setError(null);
      setResultado(null);
      setCargando(true);
      iniciarPulso();

      const foto = await cameraRef.current.takePictureAsync({
        quality: 0.25,
        base64: false,
        skipProcessing: true,
        exif: false,
      });

      const formData = new FormData();
      formData.append("imagen", {
        uri: foto.uri,
        type: "image/jpeg",
        name: "donacion.jpg",
      });

      const respuesta = await fetch(CLASIFICAR_URL, {
        method: "POST",
        body: formData,
        headers: { "Content-Type": "multipart/form-data" },
      });

      const datos = await respuesta.json();

      if (!respuesta.ok) {
        throw new Error(datos.error || `Error del servidor: ${respuesta.status}`);
      }

      setResultado(datos);
      setModalVisible(true);
    } catch (err) {
      setError(err.message || "Error desconocido al clasificar la imagen.");
      setModalVisible(true);
    } finally {
      setCargando(false);
      detenerPulso();
    }
  };

  const cambiarCategoria = (nuevaCategoria) => {
    if (!resultado) return;
    const prioridades = {
      medicamentos: "Alta",
      comida: "Alta",
      higiene: "Alta",
      limpieza: "Alta",
      agua: "Alta",
      ropa: "Media",
      calzado: "Media",
      otros: "Baja",
    };
    setResultado({
      ...resultado,
      categoria: nuevaCategoria,
      prioridad: prioridades[nuevaCategoria] || "Media",
    });
    setMensajeGuardado(null);
  };

  const guardarDonacion = async () => {
    if (!resultado || guardando) return;

    try {
      setGuardando(true);
      setMensajeGuardado(null);

      const respuesta = await fetch(DONACIONES_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          categoria: resultado.categoria,
          subcategoria: resultado.subcategoria || "",
          descripcion_corta: resultado.descripcion_corta,
          conteo_estimado: resultado.conteo_estimado,
          prioridad: resultado.prioridad,
          centro_acopio: centroAcopio,
          confirmado: true,
        }),
      });

      const datos = await respuesta.json();

      if (!respuesta.ok) {
        throw new Error(datos.error || "No se pudo guardar la donación.");
      }

      setMensajeGuardado(`Guardado con ID #${datos.id}`);
      await actualizarInventarioSilencioso();
      setModalVisible(false);
      setResultado(null);
      setMensajeGuardado(null);
    } catch (err) {
      setMensajeGuardado(err.message || "Error al guardar la donación.");
    } finally {
      setGuardando(false);
    }
  };

  const actualizarInventarioSilencioso = async () => {
    try {
      const [respuestaDonaciones, respuestaResumen] = await Promise.all([
        fetch(DONACIONES_URL),
        fetch(RESUMEN_URL),
      ]);

      const datosDonaciones = await respuestaDonaciones.json();
      const datosResumen = await respuestaResumen.json();

      if (!respuestaDonaciones.ok || !respuestaResumen.ok) {
        throw new Error("No se pudo cargar el inventario.");
      }

      setDonaciones(datosDonaciones);
      setResumen(datosResumen);
    } catch (err) {
      console.warn("Error actualizando inventario:", err.message);
    }
  };

  const cargarInventario = async () => {
    await actualizarInventarioSilencioso();
    setInventarioVisible(true);
  };

  const cargarSubcategorias = async () => {
    try {
      const respuesta = await fetch(SUBCATEGORIAS_URL);
      const datos = await respuesta.json();
      if (respuesta.ok) setSubcategorias(datos);
    } catch (err) {
      console.warn("Error cargando subcategorías:", err.message);
    }
  };

  const abrirAdmin = async () => {
    await cargarSubcategorias();
    setAdminVisible(true);
  };

  const agregarSubcategoria = async () => {
    if (!nuevaSubcategoria.trim()) return;
    try {
      const respuesta = await fetch(SUBCATEGORIAS_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ categoria: categoriaNuevaSub, nombre: nuevaSubcategoria.trim() }),
      });
      if (respuesta.ok) {
        setNuevaSubcategoria("");
        await cargarSubcategorias();
      }
    } catch (err) {
      console.warn("Error agregando subcategoría:", err.message);
    }
  };

  const guardarEdicionSubcategoria = async () => {
    if (!subcategoriaEditando || !textoEditadoSub.trim()) return;
    try {
      const respuesta = await fetch(`${SUBCATEGORIAS_URL}/${subcategoriaEditando.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre: textoEditadoSub.trim() }),
      });
      if (respuesta.ok) {
        setSubcategoriaEditando(null);
        setTextoEditadoSub("");
        await cargarSubcategorias();
        await actualizarInventarioSilencioso();
      }
    } catch (err) {
      console.warn("Error editando subcategoría:", err.message);
    }
  };

  const eliminarSubcategoria = async (id) => {
    try {
      const respuesta = await fetch(`${SUBCATEGORIAS_URL}/${id}`, { method: "DELETE" });
      if (respuesta.ok) await cargarSubcategorias();
    } catch (err) {
      console.warn("Error eliminando subcategoría:", err.message);
    }
  };

  const cerrarModal = () => {
    setModalVisible(false);
    setResultado(null);
    setError(null);
    setMensajeGuardado(null);
  };

  if (!permission) {
    return (
      <View style={styles.centrado}>
        <ActivityIndicator size="large" color="#6C63FF" />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.centrado}>
        <Text style={styles.textoPermiso}>
          📷 Esta app necesita acceso a la cámara para clasificar donaciones.
        </Text>
        <TouchableOpacity style={styles.botonPermiso} onPress={requestPermission}>
          <Text style={styles.textoBotonPermiso}>Conceder permiso</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const colorCategoria = resultado ? (CATEGORY_COLORS[resultado.categoria] ?? "#6C63FF") : "#6C63FF";
  const colorPrioridad = resultado ? (PRIORITY_COLORS[resultado.prioridad] ?? "#F4A261") : "#F4A261";
  const iconoCategoria = resultado ? (CATEGORY_ICONS[resultado.categoria] ?? "📦") : "📦";

  return (
    <View style={styles.contenedor}>
      <StatusBar style="light" />

      <CameraView style={styles.camara} ref={cameraRef} facing="back" />
      <View style={styles.overlay}>
        <View style={styles.encabezado}>
          <Text style={styles.titulo}>🤝 Clasificador de Donaciones</Text>
          <Text style={styles.subtitulo}>Centro de acopio activo</Text>
          <CentroSelect centro={centroAcopio} onChange={setCentroAcopio} />
          <View style={styles.botonesHeader}>
            <TouchableOpacity style={styles.botonHeader} onPress={cargarInventario}>
              <Text style={styles.textoBotonHeader}>📊 Inventario</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.botonHeader} onPress={abrirAdmin}>
              <Text style={styles.textoBotonHeader}>⚙️ Categorías</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.marcadorContenedor}>
          <View style={styles.marcador} />
        </View>

        <View style={styles.piePagina}>
          {cargando ? (
            <View style={styles.estadoCarga}>
              <Animated.View style={{ transform: [{ scale: pulseAnim }] }}>
                <ActivityIndicator size="large" color="#FFFFFF" />
              </Animated.View>
              <Text style={styles.textoCargando}>Analizando con IA local...</Text>
            </View>
          ) : (
            <TouchableOpacity style={styles.botonCaptura} onPress={capturarYClasificar} activeOpacity={0.8}>
              <View style={styles.botonCapturaInterno} />
            </TouchableOpacity>
          )}
        </View>
      </View>

      <Modal visible={modalVisible} transparent animationType="slide" onRequestClose={cerrarModal}>
        <Pressable style={styles.fondoModal} onPress={cerrarModal}>
          <Pressable style={styles.tarjetaContenedor} onPress={() => {}}>
            {error ? (
              <View style={styles.tarjetaError}>
                <Text style={styles.iconoTarjeta}>⚠️</Text>
                <Text style={styles.tarjetaTitulo}>Error al clasificar</Text>
                <Text style={styles.tarjetaErrorTexto}>{error}</Text>
                <TouchableOpacity style={styles.botonCerrar} onPress={cerrarModal}>
                  <Text style={styles.textoBotonCerrar}>Intentar de nuevo</Text>
                </TouchableOpacity>
              </View>
            ) : resultado ? (
              <ScrollView showsVerticalScrollIndicator={false}>
                <View style={[styles.tarjeta, { borderTopColor: colorCategoria }]}>
                  <View style={[styles.badgeCategoria, { backgroundColor: colorCategoria }]}>
                    <Text style={styles.iconoTarjeta}>{iconoCategoria}</Text>
                    <Text style={styles.textoBadge}>{resultado.categoria}</Text>
                  </View>

                  <View style={styles.filaDatos}>
                    <View style={styles.filaCampo}>
                      <Text style={styles.etiqueta}>Categoría</Text>
                      <CategoriaSelect categoria={resultado.categoria} onChange={cambiarCategoria} />
                    </View>

                    <View style={styles.separador} />

                    <View style={styles.filaCampo}>
                      <Text style={styles.etiqueta}>Subcategoría / Nombre del producto</Text>
                      <SubcategoriaSelect
                        categoria={resultado.categoria}
                        subcategoria={resultado.subcategoria}
                        onChange={(nombre) => setResultado({ ...resultado, subcategoria: nombre })}
                        onAdmin={() => {
                          setModalVisible(false);
                          abrirAdmin();
                        }}
                      />
                    </View>

                    <View style={styles.separador} />

                    <View style={styles.filaCampo}>
                      <Text style={styles.etiqueta}>Descripción (editable)</Text>
                      <TextInput
                        style={styles.inputEditable}
                        value={resultado.descripcion_corta}
                        onChangeText={(texto) => setResultado({ ...resultado, descripcion_corta: texto })}
                        multiline
                        maxLength={120}
                      />
                    </View>

                    <View style={styles.separador} />

                    <View style={styles.filaHorizontal}>
                      <View style={styles.filaCampoMitad}>
                        <Text style={styles.etiqueta}>Cantidad a registrar</Text>
                        <TextInput
                          style={styles.inputCantidad}
                          value={String(resultado.conteo_estimado)}
                          onChangeText={(texto) => {
                            const numero = parseInt(texto.replace(/[^0-9]/g, ""), 10);
                            setResultado({ ...resultado, conteo_estimado: isNaN(numero) ? 1 : numero });
                          }}
                          keyboardType="numeric"
                          maxLength={5}
                        />
                      </View>

                      <View style={styles.filaCampoMitad}>
                        <Text style={styles.etiqueta}>Prioridad</Text>
                        <View style={[styles.badgePrioridad, { backgroundColor: colorPrioridad + "22" }]}>
                          <View style={[styles.puntoPrioridad, { backgroundColor: colorPrioridad }]} />
                          <Text style={[styles.textoPrioridad, { color: colorPrioridad }]}>
                            {resultado.prioridad}
                          </Text>
                        </View>
                      </View>
                    </View>
                  </View>

                  {mensajeGuardado ? (
                    <Text style={styles.mensajeGuardado}>{mensajeGuardado}</Text>
                  ) : null}

                  <TouchableOpacity
                    style={[styles.botonGuardar, { backgroundColor: colorCategoria }]}
                    onPress={guardarDonacion}
                    disabled={guardando}
                  >
                    <Text style={styles.textoBotonCerrar}>
                      {guardando ? "Guardando..." : "💾 Guardar donación"}
                    </Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.botonSecundario}
                    onPress={cerrarModal}
                  >
                    <Text style={styles.textoBotonSecundario}>📷 Clasificar otro artículo</Text>
                  </TouchableOpacity>
                </View>
              </ScrollView>
            ) : null}
          </Pressable>
        </Pressable>
      </Modal>

      <Modal visible={inventarioVisible} transparent animationType="slide" onRequestClose={() => setInventarioVisible(false)}>
        <Pressable style={styles.fondoModal} onPress={() => setInventarioVisible(false)}>
          <Pressable style={styles.tarjetaContenedor} onPress={() => {}}>
            <View style={styles.tarjetaInventario}>
              <View style={styles.encabezadoInventario}>
                <Text style={styles.tituloInventario}>📊 Inventario compartido</Text>
                <TouchableOpacity onPress={() => setInventarioVisible(false)}>
                  <Text style={styles.cerrarInventario}>✕</Text>
                </TouchableOpacity>
              </View>

              <ScrollView showsVerticalScrollIndicator={false}>
                {resumen?.totales_por_categoria?.length ? (
                  <View style={styles.resumenGrid}>
                    {resumen.totales_por_categoria.map((item) => (
                      <View key={item.categoria} style={styles.resumenItem}>
                        <Text style={styles.resumenCategoria}>{CATEGORY_ICONS[item.categoria] ?? "📦"} {item.categoria}</Text>
                        <Text style={styles.resumenTotal}>{item.total ?? 0}</Text>
                        <Text style={styles.resumenRegistros}>{item.registros} registros</Text>
                      </View>
                    ))}
                  </View>
                ) : (
                  <Text style={styles.textoVacio}>Todavía no hay donaciones guardadas.</Text>
                )}

                {donaciones.map((item) => (
                  <View key={item.id} style={styles.itemDonacion}>
                    <Text style={styles.itemTitulo}>#{item.id} · {CATEGORY_ICONS[item.categoria] ?? "📦"} {item.categoria}{item.subcategoria ? ` · ${item.subcategoria}` : ""}</Text>
                    <Text style={styles.itemDescripcion}>{item.descripcion_corta}</Text>
                    <Text style={styles.itemMeta}>{item.conteo_estimado} uds. · Prioridad {item.prioridad} · {item.centro_acopio}</Text>
                  </View>
                ))}
              </ScrollView>
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      <Modal visible={adminVisible} transparent animationType="slide" onRequestClose={() => setAdminVisible(false)}>
        <Pressable style={styles.fondoModal} onPress={() => setAdminVisible(false)}>
          <Pressable style={styles.tarjetaContenedor} onPress={() => {}}>
            <View style={styles.tarjetaInventario}>
              <View style={styles.encabezadoInventario}>
                <Text style={styles.tituloInventario}>⚙️ Categorías y subcategorías</Text>
                <TouchableOpacity onPress={() => setAdminVisible(false)}>
                  <Text style={styles.cerrarInventario}>✕</Text>
                </TouchableOpacity>
              </View>

              <View style={styles.filaHorizontal}>
                <CategoriaSelect categoria={categoriaNuevaSub} onChange={setCategoriaNuevaSub} />
                <TextInput
                  style={[styles.inputEditable, { flex: 1, marginLeft: 8 }]}
                  value={nuevaSubcategoria}
                  onChangeText={setNuevaSubcategoria}
                  placeholder="Nueva subcategoría"
                  maxLength={60}
                />
                <TouchableOpacity style={styles.botonAgregarSub} onPress={agregarSubcategoria}>
                  <Text style={styles.textoBotonAgregarSub}>+</Text>
                </TouchableOpacity>
              </View>

              <ScrollView showsVerticalScrollIndicator={false} style={{ marginTop: 12 }}>
                {subcategorias.length === 0 ? (
                  <Text style={styles.textoVacio}>No hay subcategorías registradas.</Text>
                ) : (
                  subcategorias.map((item) => (
                    <View key={item.id} style={styles.itemSubcategoria}>
                      {subcategoriaEditando?.id === item.id ? (
                        <View style={styles.filaHorizontal}>
                          <TextInput
                            style={[styles.inputEditable, { flex: 1 }]}
                            value={textoEditadoSub}
                            onChangeText={setTextoEditadoSub}
                            autoFocus
                            maxLength={60}
                          />
                          <TouchableOpacity onPress={guardarEdicionSubcategoria}>
                            <Text style={styles.iconoAdmin}>✓</Text>
                          </TouchableOpacity>
                          <TouchableOpacity onPress={() => { setSubcategoriaEditando(null); setTextoEditadoSub(""); }}>
                            <Text style={styles.iconoAdmin}>✕</Text>
                          </TouchableOpacity>
                        </View>
                      ) : (
                        <View style={styles.filaHorizontal}>
                          <Text style={styles.textoSubcategoria}>{CATEGORY_ICONS[item.categoria] ?? "📦"} {item.categoria} · {item.nombre}</Text>
                          <TouchableOpacity onPress={() => { setSubcategoriaEditando(item); setTextoEditadoSub(item.nombre); }}>
                            <Text style={styles.iconoAdmin}>✏️</Text>
                          </TouchableOpacity>
                          <TouchableOpacity onPress={() => eliminarSubcategoria(item.id)}>
                            <Text style={styles.iconoAdmin}>🗑️</Text>
                          </TouchableOpacity>
                        </View>
                      )}
                    </View>
                  ))
                )}
              </ScrollView>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  contenedor: { flex: 1, backgroundColor: "#000" },
  camara: { flex: 1 },
  overlay: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "transparent", flexDirection: "column", justifyContent: "space-between" },
  encabezado: { paddingTop: 60, paddingHorizontal: 24, paddingBottom: 16, backgroundColor: "rgba(0,0,0,0.55)", alignItems: "center" },
  titulo: { color: "#FFFFFF", fontSize: 20, fontWeight: "700", letterSpacing: 0.5 },
  subtitulo: { color: "rgba(255,255,255,0.75)", fontSize: 13, marginTop: 4 },
  botonesHeader: { flexDirection: "row", gap: 10, marginTop: 10 },
  botonHeader: { backgroundColor: "rgba(255,255,255,0.16)", paddingHorizontal: 14, paddingVertical: 8, borderRadius: 16 },
  textoBotonHeader: { color: "#FFFFFF", fontWeight: "700", fontSize: 13 },
  botonInventario: { marginTop: 10, backgroundColor: "rgba(255,255,255,0.16)", paddingHorizontal: 14, paddingVertical: 8, borderRadius: 16 },
  textoBotonInventario: { color: "#FFFFFF", fontWeight: "700", fontSize: 13 },
  marcadorContenedor: { flex: 1, justifyContent: "center", alignItems: "center" },
  marcador: { width: width * 0.72, height: width * 0.72, borderWidth: 2, borderColor: "rgba(255,255,255,0.5)", borderRadius: 16, borderStyle: "dashed" },
  piePagina: { paddingBottom: 48, alignItems: "center", backgroundColor: "rgba(0,0,0,0.45)", paddingTop: 24 },
  botonCaptura: { width: 76, height: 76, borderRadius: 38, backgroundColor: "rgba(255,255,255,0.25)", borderWidth: 3, borderColor: "#FFFFFF", justifyContent: "center", alignItems: "center" },
  botonCapturaInterno: { width: 54, height: 54, borderRadius: 27, backgroundColor: "#FFFFFF" },
  estadoCarga: { alignItems: "center", gap: 12 },
  textoCargando: { color: "#FFFFFF", fontSize: 15, fontWeight: "600" },
  centrado: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#1a1a2e", padding: 32 },
  textoPermiso: { color: "#FFFFFF", fontSize: 16, textAlign: "center", lineHeight: 24, marginBottom: 24 },
  botonPermiso: { backgroundColor: "#6C63FF", paddingHorizontal: 28, paddingVertical: 14, borderRadius: 12 },
  textoBotonPermiso: { color: "#FFFFFF", fontWeight: "700", fontSize: 16 },
  fondoModal: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "flex-end" },
  tarjetaContenedor: { backgroundColor: "transparent", maxHeight: "75%" },
  tarjeta: { backgroundColor: "#FFFFFF", borderRadius: 24, borderTopWidth: 6, marginHorizontal: 12, marginBottom: 20, padding: 24, shadowColor: "#000", shadowOffset: { width: 0, height: -4 }, shadowOpacity: 0.15, shadowRadius: 12, elevation: 12 },
  tarjetaError: { backgroundColor: "#FFFFFF", borderRadius: 24, borderTopWidth: 6, borderTopColor: "#E63946", marginHorizontal: 12, marginBottom: 20, padding: 24, alignItems: "center" },
  badgeCategoria: { flexDirection: "row", alignItems: "center", alignSelf: "flex-start", paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, marginBottom: 20, gap: 8 },
  iconoTarjeta: { fontSize: 24 },
  textoBadge: { color: "#FFFFFF", fontWeight: "700", fontSize: 16 },
  filaDatos: { gap: 8 },
  filaCampo: { gap: 4 },
  filaHorizontal: { flexDirection: "row", gap: 16, marginTop: 8 },
  filaCampoMitad: { flex: 1, gap: 6 },
  etiqueta: { fontSize: 11, fontWeight: "600", color: "#9E9E9E", textTransform: "uppercase", letterSpacing: 0.8 },
  valor: { fontSize: 16, color: "#212121", fontWeight: "500", lineHeight: 22 },
  separador: { height: 1, backgroundColor: "#F0F0F0", marginVertical: 4 },
  badgeConteo: { flexDirection: "row", alignItems: "baseline" },
  textoConteo: { fontSize: 28, fontWeight: "800", color: "#212121" },
  textoUnidad: { fontSize: 14, color: "#757575", fontWeight: "500" },
  badgePrioridad: { flexDirection: "row", alignItems: "center", alignSelf: "flex-start", paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10, gap: 6, marginTop: 2 },
  puntoPrioridad: { width: 8, height: 8, borderRadius: 4 },
  textoPrioridad: { fontWeight: "700", fontSize: 14 },
  tarjetaTitulo: { fontSize: 18, fontWeight: "700", color: "#212121", marginTop: 8, marginBottom: 8 },
  tarjetaErrorTexto: { fontSize: 14, color: "#757575", textAlign: "center", lineHeight: 20, marginBottom: 20 },
  mensajeGuardado: { marginTop: 16, color: "#2DC653", fontWeight: "700", textAlign: "center" },
  inputEditable: { backgroundColor: "#F5F5F5", borderRadius: 10, borderWidth: 1, borderColor: "#E0E0E0", paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: "#212121", marginTop: 6, minHeight: 54, textAlignVertical: "top" },
  inputCantidad: { backgroundColor: "#F5F5F5", borderRadius: 10, borderWidth: 1, borderColor: "#E0E0E0", paddingHorizontal: 12, paddingVertical: 10, fontSize: 18, fontWeight: "800", color: "#212121", marginTop: 6, textAlign: "center" },
  selectBoton: { flexDirection: "row", alignItems: "center", backgroundColor: "#F5F5F5", borderRadius: 12, borderWidth: 1.5, paddingHorizontal: 14, paddingVertical: 12, marginTop: 8, gap: 10 },
  selectIcono: { fontSize: 20 },
  selectTexto: { flex: 1, fontSize: 15, fontWeight: "700", color: "#212121" },
  selectFlecha: { fontSize: 16, color: "#757575", fontWeight: "700" },
  selectFondo: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "center", alignItems: "center", padding: 24 },
  selectTarjeta: { backgroundColor: "#FFFFFF", borderRadius: 20, padding: 16, width: "100%", maxHeight: "70%" },
  selectTitulo: { fontSize: 16, fontWeight: "800", color: "#212121", marginBottom: 12, textAlign: "center" },
  selectItem: { flexDirection: "row", alignItems: "center", paddingVertical: 12, paddingHorizontal: 10, borderRadius: 12, gap: 12 },
  selectItemIcono: { fontSize: 20, width: 28 },
  selectItemTexto: { flex: 1, fontSize: 15, fontWeight: "600", color: "#424242" },
  selectCheck: { fontSize: 16, fontWeight: "800" },
  botonGuardar: { marginTop: 20, paddingVertical: 14, borderRadius: 12, alignItems: "center" },
  botonCerrar: { marginTop: 20, paddingVertical: 14, borderRadius: 12, alignItems: "center", backgroundColor: "#6C63FF" },
  botonSecundario: { marginTop: 10, paddingVertical: 12, borderRadius: 12, alignItems: "center", backgroundColor: "#F5F5F5" },
  textoBotonSecundario: { color: "#424242", fontWeight: "700", fontSize: 15 },
  textoBotonCerrar: { color: "#FFFFFF", fontWeight: "700", fontSize: 15 },
  botonAgregarSub: { backgroundColor: "#6C63FF", width: 42, height: 42, borderRadius: 10, justifyContent: "center", alignItems: "center", marginLeft: 8 },
  textoBotonAgregarSub: { color: "#FFFFFF", fontWeight: "800", fontSize: 22 },
  itemSubcategoria: { backgroundColor: "#F7F7FA", borderRadius: 12, padding: 10, marginBottom: 8 },
  textoSubcategoria: { flex: 1, fontSize: 14, color: "#212121", fontWeight: "600" },
  iconoAdmin: { fontSize: 18, paddingHorizontal: 8 },
  tarjetaInventario: { backgroundColor: "#FFFFFF", borderRadius: 24, marginHorizontal: 12, marginBottom: 20, padding: 20, maxHeight: "82%" },
  encabezadoInventario: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  tituloInventario: { fontSize: 19, fontWeight: "800", color: "#212121" },
  cerrarInventario: { fontSize: 24, color: "#757575", fontWeight: "700" },
  resumenGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginBottom: 18 },
  resumenItem: { width: "47%", backgroundColor: "#F7F7FA", padding: 12, borderRadius: 14 },
  resumenCategoria: { fontSize: 13, color: "#616161", fontWeight: "700" },
  resumenTotal: { fontSize: 28, color: "#212121", fontWeight: "900", marginTop: 4 },
  resumenRegistros: { fontSize: 11, color: "#9E9E9E", marginTop: 2 },
  textoVacio: { color: "#757575", fontSize: 15, textAlign: "center", marginVertical: 24 },
  itemDonacion: { borderTopWidth: 1, borderTopColor: "#EEEEEE", paddingVertical: 12 },
  itemTitulo: { fontSize: 15, fontWeight: "800", color: "#212121" },
  itemDescripcion: { fontSize: 14, color: "#424242", marginTop: 4 },
  itemMeta: { fontSize: 12, color: "#757575", marginTop: 4 },
});
