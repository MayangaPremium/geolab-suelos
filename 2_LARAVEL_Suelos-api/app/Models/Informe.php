<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Informe extends Model
{
    protected $fillable = [
        'user_id', 'uid', 'proyecto', 'muestra', 'ensayo', 'tipo_ensayo', 'tipo',
        'origen', 'archivo_pdf', 'datos', 'resultados', 'clasificacion',
    ];

    protected $casts = [
        'datos' => 'array',
        'resultados' => 'array',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }
}
