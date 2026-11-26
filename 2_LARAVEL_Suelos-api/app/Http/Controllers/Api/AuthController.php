<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\User;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;

class AuthController extends Controller
{
    /**
     * Registro de usuarios.
     * Para controlar quien puede registrarse, define en .env:  REGISTRO_CODIGO=una-clave-del-grupo
     * (y en config/app.php agrega:  'registro_codigo' => env('REGISTRO_CODIGO'),  ).
     * Si no se define, el registro queda abierto.
     */
    public function register(Request $request): JsonResponse
    {
        $codigoRequerido = config('app.registro_codigo', env('REGISTRO_CODIGO'));

        $data = $request->validate([
            'name' => 'required|string|max:255',
            'email' => 'required|email|max:255|unique:users,email',
            'password' => 'required|string|min:8',
            'codigo' => 'nullable|string',
            'dispositivo' => 'nullable|string|max:40',
        ]);

        if ($codigoRequerido && ! hash_equals((string) $codigoRequerido, (string) ($data['codigo'] ?? ''))) {
            return response()->json(['message' => 'Código de registro incorrecto.'], 403);
        }

        $user = User::create([
            'name' => $data['name'],
            'email' => $data['email'],
            'password' => Hash::make($data['password']),
        ]);

        return response()->json([
            'token' => $user->createToken('geolab-' . ($data['dispositivo'] ?? 'app'))->plainTextToken,
            'user' => ['id' => $user->id, 'name' => $user->name, 'email' => $user->email],
        ], 201);
    }

    public function login(Request $request): JsonResponse
    {
        $data = $request->validate([
            'email' => 'required|email',
            'password' => 'required|string',
            'dispositivo' => 'nullable|string|max:40',
        ]);

        $user = User::where('email', $data['email'])->first();

        if (! $user || ! Hash::check($data['password'], $user->password)) {
            return response()->json(['message' => 'Correo o contraseña incorrectos.'], 401);
        }

        $nombreToken = 'geolab-' . ($data['dispositivo'] ?? 'app');
        // Un token por dispositivo (escritorio y web pueden estar abiertos a la vez).
        $user->tokens()->where('name', $nombreToken)->delete();

        return response()->json([
            'token' => $user->createToken($nombreToken)->plainTextToken,
            'user' => ['id' => $user->id, 'name' => $user->name, 'email' => $user->email],
        ]);
    }

    public function logout(Request $request): JsonResponse
    {
        $request->user()->currentAccessToken()->delete();

        return response()->json(['message' => 'Sesión cerrada.']);
    }

    public function me(Request $request): JsonResponse
    {
        $u = $request->user();

        return response()->json(['id' => $u->id, 'name' => $u->name, 'email' => $u->email]);
    }
}
