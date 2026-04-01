import { CameraView, useCameraPermissions } from "expo-camera";
import { StatusBar } from "expo-status-bar";
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

type Rabbit = {
  id: number;
  name: string;
  status: string;
  photo_url?: string | null;
};

type PairingResponse = {
  ok: boolean;
  api_token: string;
  user: { email: string };
  rabbits: Rabbit[];
};

const extractPairingToken = (value: string): string => {
  const trimmed = value.trim();
  const match = trimmed.match(/\/mobile-app\/pair\/([^/?#]+)/);
  return match?.[1] ?? "";
};

export default function App() {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanMode, setScanMode] = useState(false);
  const [pairingToken, setPairingToken] = useState("");
  const [apiBaseUrl, setApiBaseUrl] = useState("https://nabaztag.org");
  const [apiToken, setApiToken] = useState("");
  const [rabbits, setRabbits] = useState<Rabbit[]>([]);
  const [selectedRabbitId, setSelectedRabbitId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const selectedRabbit = useMemo(
    () => rabbits.find((rabbit) => rabbit.id === selectedRabbitId) ?? null,
    [rabbits, selectedRabbitId]
  );

  useEffect(() => {
    if (!selectedRabbit && rabbits.length) {
      setSelectedRabbitId(rabbits[0].id);
    }
  }, [rabbits, selectedRabbit]);

  const claimPairing = async (tokenValue: string) => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBaseUrl}/mobile-api/v1/pairing/claim`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pairing_token: tokenValue,
          device_name: "Téléphone Nabaztag",
        }),
      });
      const data = (await response.json()) as PairingResponse & { message?: string };
      if (!response.ok || !data.ok) {
        throw new Error(data.message || "Appairage impossible.");
      }
      setApiToken(data.api_token);
      setRabbits(data.rabbits || []);
      setReply("");
      setScanMode(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur d'appairage.");
    } finally {
      setLoading(false);
    }
  };

  const refreshRabbits = async () => {
    if (!apiToken) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBaseUrl}/mobile-api/v1/rabbits`, {
        headers: { Authorization: `Bearer ${apiToken}` },
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.message || "Impossible de charger les lapins.");
      }
      setRabbits(data.rabbits || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de synchronisation.");
    } finally {
      setLoading(false);
    }
  };

  const sendConversation = async () => {
    if (!apiToken || !selectedRabbitId || !message.trim()) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBaseUrl}/mobile-api/v1/rabbits/${selectedRabbitId}/conversation`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: message }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.message || "Le lapin n'a pas répondu.");
      }
      setReply(data.reply || "");
      setMessage("");
      await refreshRabbits();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de conversation.");
    } finally {
      setLoading(false);
    }
  };

  if (scanMode) {
    return (
      <SafeAreaView style={styles.screen}>
        <StatusBar style="dark" />
        <View style={styles.section}>
          <Text style={styles.title}>Scanner le QR code</Text>
          <Text style={styles.meta}>Scanne le QR généré dans Mon compte sur nabaztag.org.</Text>
        </View>
        {!permission ? (
          <ActivityIndicator />
        ) : !permission.granted ? (
          <View style={styles.section}>
            <Pressable style={styles.button} onPress={requestPermission}>
              <Text style={styles.buttonText}>Autoriser la caméra</Text>
            </Pressable>
          </View>
        ) : (
          <CameraView
            style={styles.camera}
            barcodeScannerSettings={{ barcodeTypes: ["qr"] }}
            onBarcodeScanned={({ data }) => {
              const tokenValue = extractPairingToken(data);
              if (!tokenValue || loading) return;
              setPairingToken(tokenValue);
              void claimPairing(tokenValue);
            }}
          />
        )}
        <Pressable style={styles.secondaryButton} onPress={() => setScanMode(false)}>
          <Text style={styles.secondaryButtonText}>Annuler</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.section}>
          <Text style={styles.title}>OK Nabaztag</Text>
          <Text style={styles.meta}>
            MVP mobile : scan du QR, liste des lapins, statut, et envoi de texte vers le pipeline de conversation existant.
          </Text>
        </View>

        {!apiToken ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Appairer l’application</Text>
            <TextInput
              style={styles.input}
              value={apiBaseUrl}
              onChangeText={setApiBaseUrl}
              autoCapitalize="none"
              placeholder="https://nabaztag.org"
            />
            <TextInput
              style={styles.input}
              value={pairingToken}
              onChangeText={setPairingToken}
              autoCapitalize="none"
              placeholder="Code d'appairage ou URL scannée"
            />
            <Pressable style={styles.button} onPress={() => setScanMode(true)}>
              <Text style={styles.buttonText}>Scanner le QR code</Text>
            </Pressable>
            <Pressable
              style={styles.secondaryButton}
              onPress={() => {
                const tokenValue = extractPairingToken(pairingToken) || pairingToken.trim();
                if (tokenValue) {
                  void claimPairing(tokenValue);
                }
              }}
            >
              <Text style={styles.secondaryButtonText}>Appairer manuellement</Text>
            </Pressable>
          </View>
        ) : (
          <>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Mes lapins</Text>
              <FlatList
                data={rabbits}
                keyExtractor={(item) => String(item.id)}
                scrollEnabled={false}
                renderItem={({ item }) => (
                  <Pressable
                    style={[styles.rabbitRow, item.id === selectedRabbitId && styles.rabbitRowSelected]}
                    onPress={() => setSelectedRabbitId(item.id)}
                  >
                    <Text style={styles.rabbitName}>{item.name}</Text>
                    <Text style={styles.rabbitStatus}>{item.status}</Text>
                  </Pressable>
                )}
              />
              <Pressable style={styles.secondaryButton} onPress={() => void refreshRabbits()}>
                <Text style={styles.secondaryButtonText}>Actualiser le statut</Text>
              </Pressable>
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>
                {selectedRabbit ? `Parler à ${selectedRabbit.name}` : "Choisis un lapin"}
              </Text>
              <TextInput
                style={[styles.input, styles.multiline]}
                value={message}
                onChangeText={setMessage}
                multiline
                placeholder="Dis quelque chose au lapin…"
              />
              <Pressable style={styles.button} onPress={() => void sendConversation()}>
                <Text style={styles.buttonText}>Envoyer au lapin</Text>
              </Pressable>
              <Text style={styles.meta}>
                Étape suivante : remplacer cette zone par une vraie reconnaissance vocale locale et un wake phrase `OK Nabaztag`.
              </Text>
              {!!reply && (
                <View style={styles.replyBox}>
                  <Text style={styles.replyTitle}>Réponse générée</Text>
                  <Text>{reply}</Text>
                </View>
              )}
            </View>
          </>
        )}

        {!!loading && <ActivityIndicator style={{ marginTop: 12 }} />}
        {!!error && <Text style={styles.error}>{error}</Text>}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#f4f1eb" },
  container: { padding: 20, gap: 16 },
  section: { gap: 8 },
  title: { fontSize: 28, fontWeight: "800", color: "#181715" },
  meta: { color: "#6f695f", lineHeight: 20 },
  card: {
    backgroundColor: "rgba(255,255,255,0.82)",
    borderWidth: 1,
    borderColor: "rgba(24,23,21,0.08)",
    padding: 16,
    gap: 12,
  },
  cardTitle: { fontSize: 18, fontWeight: "700", color: "#181715" },
  input: {
    borderWidth: 1,
    borderColor: "rgba(24,23,21,0.12)",
    backgroundColor: "white",
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  multiline: { minHeight: 110, textAlignVertical: "top" },
  button: {
    backgroundColor: "#2d8a5f",
    paddingHorizontal: 14,
    paddingVertical: 12,
    alignItems: "center",
  },
  buttonText: { color: "white", fontWeight: "700" },
  secondaryButton: {
    borderWidth: 1,
    borderColor: "rgba(24,23,21,0.12)",
    paddingHorizontal: 14,
    paddingVertical: 12,
    alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.5)",
  },
  secondaryButtonText: { color: "#181715", fontWeight: "600" },
  rabbitRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 10,
    backgroundColor: "rgba(255,255,255,0.7)",
    borderWidth: 1,
    borderColor: "rgba(24,23,21,0.06)",
    marginBottom: 8,
  },
  rabbitRowSelected: { borderColor: "#2d8a5f", backgroundColor: "rgba(45,138,95,0.08)" },
  rabbitName: { fontWeight: "700", color: "#181715" },
  rabbitStatus: { color: "#6f695f" },
  replyBox: {
    marginTop: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: "rgba(24,23,21,0.08)",
    backgroundColor: "rgba(255,255,255,0.76)",
    gap: 6,
  },
  replyTitle: { fontWeight: "700" },
  error: { color: "#a64e17", marginTop: 8 },
  camera: { flex: 1, minHeight: 420, margin: 20, borderRadius: 12, overflow: "hidden" },
});
