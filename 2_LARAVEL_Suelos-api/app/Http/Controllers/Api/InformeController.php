<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Informe;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Schema;

class InformeController extends Controller
{
    /** Lista los informes del usuario (sin el detalle pesado). Filtros: ensayo, proyecto, muestra, desde, hasta. */
    public function index(Request $request)
    {
        $q = Informe::where('user_id', $request->user()->id)
            ->select(['id', 'uid', 'proyecto', 'muestra', 'ensayo', 'tipo', 'origen',
                      'archivo_pdf', 'resultados', 'clasificacion', 'created_at']);

        if ($request->filled('ensayo')) {
            $q->where('ensayo', (string) $request->input('ensayo'));
        }
        if ($request->filled('proyecto')) {
            $q->where('proyecto', 'like', '%' . $request->input('proyecto') . '%');
        }
        if ($request->filled('muestra')) {
            $q->where('muestra', 'like', '%' . $request->input('muestra') . '%');
        }
        if ($request->filled('desde')) {
            $q->whereDate('created_at', '>=', $request->input('desde'));
        }
        if ($request->filled('hasta')) {
            $q->whereDate('created_at', '<=', $request->input('hasta'));
        }

        $porPagina = min(max((int) $request->input('por_pagina', 50), 1), 100);

        return $q->latest()->paginate($porPagina);
    }

    /** Guarda un informe. Si llega el mismo `uid` otra vez (reintento), devuelve el ya guardado. */
    public function store(Request $request): JsonResponse
    {
        // Compatibilidad con pruebas antiguas que enviaban `tipo_ensayo`.
        if (! $request->filled('ensayo') && $request->filled('tipo_ensayo')) {
            $request->merge(['ensayo' => $request->input('tipo_ensayo')]);
        }

        $data = $request->validate([
            'uid' => 'nullable|string|max:64',
            'proyecto' => 'required|string|max:255',
            'muestra' => 'nullable|string|max:100',
            'ensayo' => 'required|string|max:50',
            'tipo' => 'nullable|in:individual,consolidado',
            'origen' => 'nullable|in:escritorio,web',
            'archivo_pdf' => 'nullable|string|max:255',
            'datos' => 'nullable|array',
            'resultados' => 'nullable|array',
            'clasificacion' => 'nullable|string|max:255',
        ]);

        $userId = $request->user()->id;

        if (! empty($data['uid'])) {
            $existente = Informe::where('user_id', $userId)->where('uid', $data['uid'])->first();
            if ($existente) {
                return response()->json($existente, 200);
            }
        }

        $data['user_id'] = $userId;
        $data['tipo'] = $data['tipo'] ?? 'individual';
        $data['origen'] = $data['origen'] ?? 'web';

        if (Schema::hasColumn('informes', 'tipo_ensayo')) {
            $data['tipo_ensayo'] = $data['ensayo'];
        }

        return response()->json(Informe::create($data), 201);
    }

    public function show(Request $request, int $id): JsonResponse
    {
        $informe = Informe::where('user_id', $request->user()->id)->findOrFail($id);

        return response()->json($informe);
    }

    public function destroy(Request $request, int $id): JsonResponse
    {
        Informe::where('user_id', $request->user()->id)->findOrFail($id)->delete();

        return response()->json(['message' => 'Informe eliminado.']);
    }
}
