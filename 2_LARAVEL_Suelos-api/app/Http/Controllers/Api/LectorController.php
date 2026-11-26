<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;

class LectorController extends Controller
{
    private const TAMICES = ['3in', '2in', '1_5in', '1in', '3_4in', '1_2in', '3_8in', '1_4in', 'n4', 'n10',
        'n20', 'n30', 'n40', 'n60', 'n100', 'n140', 'n200', 'pan'];

    public function leer(Request $request): JsonResponse
    {
        set_time_limit(180);

        $in = $request->validate([
            'data' => 'required|string',
            'mediaType' => 'required|in:image/jpeg,image/png,image/webp,image/gif,application/pdf',
            'ensayo' => 'nullable|in:granulometria',
        ]);

        $key = config('services.gemini.key', env('GEMINI_API_KEY'));
        if (! $key) {
            return response()->json(['message' => 'Falta configurar GEMINI_API_KEY en el archivo .env de Laravel.'], 500);
        }
        if (strlen($in['data']) > 10_000_000) {
            return response()->json(['message' => 'El archivo es demasiado grande. Use una foto más liviana o un PDF de menos de ~6 MB.'], 413);
        }

        $ensayo = $in['ensayo'] ?? 'granulometria';

        // Prueba primero los modelos con mayor disponibilidad gratuita antes de llegar a 3.8-flash
        $modelos = [
            'gemini-3.7-flash',
            'gemini-3.6-flash',
            'gemini-3.5-flash-lite',
            'gemini-3.1-flash-lite',
            'gemini-3.8-flash',
        ];

        $resp = null;
        $ultimoError = 'Todos los modelos gratuitos de Gemini están ocupados en este momento.';

        foreach ($modelos as $modelo) {
            try {
                $resp = Http::withHeaders(['x-goog-api-key' => $key])
                    ->acceptJson()
                    ->timeout(60)
                    ->post("https://generativelanguage.googleapis.com/v1beta/models/{$modelo}:generateContent", [
                        'contents' => [[
                            'parts' => [
                                [
                                    'inline_data' => [
                                        'mime_type' => $in['mediaType'],
                                        'data' => $in['data'],
                                    ],
                                ],
                                [
                                    'text' => $this->promptDe($ensayo),
                                ],
                            ],
                        ]],
                        'generationConfig' => [
                            'response_mime_type' => 'application/json',
                            'temperature' => 0.1,
                        ],
                    ]);
            } catch (\Throwable $e) {
                $ultimoError = 'Error de conexión con Gemini: ' . $e->getMessage();
                continue;
            }

            if ($resp->successful()) {
                break;
            }

            $ultimoError = $resp->json('error.message') ?: $ultimoError;

            // Si el modelo no existe (404) o está saturado (429/503), pasa de inmediato al siguiente
            if (in_array($resp->status(), [404, 429, 503], true)) {
                usleep(300000);
                continue;
            }

            return response()->json(['message' => "[{$modelo}] " . $ultimoError], 502);
        }

        if (! $resp || $resp->failed()) {
            return response()->json(['message' => $ultimoError], 502);
        }

        $texto = $resp->json('candidates.0.content.parts.0.text', '');
        if (! preg_match('/\{[\s\S]*\}/', $texto, $m)) {
            return response()->json(['message' => 'No se pudo interpretar la respuesta de la lectura.'], 502);
        }
        $datos = json_decode($m[0], true);
        if (! is_array($datos)) {
            return response()->json(['message' => 'La lectura devolvió un formato inválido. Intente de nuevo.'], 502);
        }

        return response()->json($datos);
    }

    private function promptDe(string $ensayo): string
    {
        $ids = implode(', ', self::TAMICES);

        return <<<PROMPT
Eres un asistente de laboratorio de mecánica de suelos. La imagen/PDF es una hoja de datos de un ensayo de granulometría por tamizado (formato UNI FIC AT-PR.4-F1 u otro similar). Los valores suelen estar ESCRITOS A MANO: lee dígito por dígito con cuidado (un 1 puede parecer 7, un 4 un 9, un 0 un 6) y no confundas el punto decimal.
Extrae SOLO lo que se vea escrito; si un dato no aparece o no se lee con seguridad, usa null. Nunca inventes ni "corrijas" números, aunque no cuadren. Usa punto decimal y números sin unidades.
Devuelve ÚNICAMENTE un objeto JSON (sin texto adicional, sin markdown) con esta forma:
{
 "metodo": "a-simple" | "a-compuesto" | "b-simple" | null,
 "columnas": "1" | "2" | null,
 "encabezado": {"informe":null,"calicata":null,"muestra":null,"profundidad":null,"fecha":"AAAA-MM-DD o null","tecnico":null,"horno":null,"balanza":null,"masa-total":null,"masa-gruesa":null,"masa-fina":null,"recipiente":null},
 "secado": {"g1":null,"g2":null,"g3":null,"f1":null,"f2":null,"f3":null},
 "masa_total": null,
 "masa_lavada": null,
 "tamices": { "<id>": {"m1": null, "m2": null} }
}
Reglas:
- "metodo": A simple = T.M. menor a 3/4"; A compuesto = T.M. mayor a 3/4" (parte gruesa + parte fina); B simple = T.M. menor a N°4. Usa el método que tenga la casilla marcada.
- "columnas": en compuesto, "2" si hay columnas de masa 1 (gruesa) y masa 2 (fina); "1" si hay una sola columna.
- "secado": masas en g de la parte gruesa (g) y fina (f). 1 = masa húmeda (inicial), 2 = masa seca, 3 = masa lavada y seca (la última, tras "lavado y secado").
- "masa_total"/"masa_lavada": masa seca total y masa seca lavada (g), solo para tamizado de una columna.
- "recipiente": texto tal como está escrito en "Masa Recipiente" (puede haber dos recipientes).
- "m1" es la masa retenida de la columna 1 (o única) y "m2" la de la columna 2 (null si no hay). Una fila puede tener valor en ambas columnas (por ejemplo N°10).
- Si una celda está tachada o tiene una raya diagonal sin número, es null.
Los ids de tamiz válidos son exactamente: {$ids} (3", 2", 1 1/2", 1", 3/4", 1/2", 3/8", 1/4", N°4, N°10, N°20, N°30, N°40, N°60, N°100, N°140, N°200 y platillo/fondo = pan).
PROMPT;
    }
}