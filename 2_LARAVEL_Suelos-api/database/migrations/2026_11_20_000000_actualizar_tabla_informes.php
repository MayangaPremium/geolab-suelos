<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Deja la tabla `informes` lista para GeoLab (escritorio y web).
 * Es SEGURA: no borra nada y solo agrega las columnas que falten,
 * por lo que conserva los informes de prueba que ya tengas.
 */
return new class extends Migration
{
    public function up(): void
    {
        if (! Schema::hasTable('informes')) {
            Schema::create('informes', function (Blueprint $t) {
                $t->id();
                $t->timestamps();
            });
        }

        Schema::table('informes', function (Blueprint $t) {
            if (! Schema::hasColumn('informes', 'user_id')) {
                $t->foreignId('user_id')->nullable()->constrained()->cascadeOnDelete();
            }
            if (! Schema::hasColumn('informes', 'uid')) {
                $t->string('uid', 64)->nullable()->index();      // evita duplicados al reenviar
            }
            if (! Schema::hasColumn('informes', 'proyecto')) {
                $t->string('proyecto')->default('');
            }
            if (! Schema::hasColumn('informes', 'muestra')) {
                $t->string('muestra', 100)->nullable();
            }
            if (! Schema::hasColumn('informes', 'ensayo')) {
                $t->string('ensayo', 50)->default('');            // humedad, volumetrico, gravedad, granulometria, atterberg, clasificacion, proctor, consolidado
            }
            if (! Schema::hasColumn('informes', 'tipo')) {
                $t->string('tipo', 20)->default('individual');    // individual | consolidado
            }
            if (! Schema::hasColumn('informes', 'origen')) {
                $t->string('origen', 20)->default('web');         // escritorio | web
            }
            if (! Schema::hasColumn('informes', 'archivo_pdf')) {
                $t->string('archivo_pdf')->nullable();
            }
            if (! Schema::hasColumn('informes', 'datos')) {
                $t->json('datos')->nullable();
            }
            if (! Schema::hasColumn('informes', 'resultados')) {
                $t->json('resultados')->nullable();
            }
            if (! Schema::hasColumn('informes', 'clasificacion')) {
                $t->string('clasificacion')->nullable();
            }
        });

        // Si una version anterior de la tabla tenia `tipo_ensayo` obligatorio, se vuelve opcional.
        if (Schema::hasColumn('informes', 'tipo_ensayo')) {
            Schema::table('informes', function (Blueprint $t) {
                $t->string('tipo_ensayo')->nullable()->change();
            });
        }
    }

    public function down(): void
    {
        // Intencionalmente vacio: no se borran columnas con informes guardados.
    }
};
