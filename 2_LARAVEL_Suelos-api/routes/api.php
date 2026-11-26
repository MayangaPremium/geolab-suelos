<?php

use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\InformeController;
use App\Http\Controllers\Api\LectorController;
use Illuminate\Support\Facades\Route;

// Acceso (con limite de intentos para evitar adivinar contraseñas)
Route::post('/register', [AuthController::class, 'register'])->middleware('throttle:10,1');
Route::post('/login', [AuthController::class, 'login'])->middleware('throttle:10,1');

// Todo lo demas exige un token valido
Route::middleware('auth:sanctum')->group(function () {
    Route::get('/me', [AuthController::class, 'me']);
    Route::post('/logout', [AuthController::class, 'logout']);

    Route::get('/informes', [InformeController::class, 'index']);
    Route::post('/informes', [InformeController::class, 'store']);
    Route::get('/informes/{id}', [InformeController::class, 'show'])->whereNumber('id');
    Route::delete('/informes/{id}', [InformeController::class, 'destroy'])->whereNumber('id');

    // Lector de hojas escaneadas (IA). Máx. 20 lecturas por hora por usuario.
    Route::post('/leer-formato', [LectorController::class, 'leer'])->middleware('throttle:20,60');
});
