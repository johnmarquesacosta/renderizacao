import os
import requests
import json
from typing import Optional, Dict, Any, Union
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

class Transcriber:
    """
    Utilitário para transcrição de áudio e vídeo usando a API v1.
    Documentação: https://github.com/stephengpope/no-code-architects-toolkit/blob/main/docs/media/media_transcribe.md
    """

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        self.api_url = api_url or os.getenv("TRANSCRIBE_API_URL")
        self.api_key = api_key or os.getenv("TRANSCRIBE_API_KEY")

        if not self.api_url:
            self.api_url = "https://api.example.com/v1/media/transcribe"
        
        # Se a URL fornecida parecer ser apenas o host/porta, anexa o path padrão da API
        if "v1/media/transcribe" not in self.api_url:
            self.api_url = self.api_url.rstrip("/") + "/v1/media/transcribe"

    def transcribe(
        self,
        media_url: str,
        task: str = "transcribe",
        include_text: bool = True,
        include_srt: bool = False,
        include_segments: bool = False,
        word_timestamps: bool = False,
        response_type: str = "direct",
        webhook_url: Optional[str] = None,
        job_id: Optional[str] = None,
        max_words_per_line: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Solicita a transcrição de um arquivo de mídia.

        Args:
            media_url: URL pública do arquivo de áudio ou vídeo.
            task: "transcribe" ou "translate".
            include_text: Incluir transcrição em texto puro.
            include_srt: Incluir legendas formatadas em SRT.
            include_segments: Incluir segmentos com timestamps.
            word_timestamps: Incluir timestamps para cada palavra individual.
            response_type: "direct" (espera o resultado) ou "cloud" (retorna URLs).
            webhook_url: URL para receber o resultado de forma assíncrona.
            job_id: Identificador customizado para o trabalho.
            max_words_per_line: Máximo de palavras por linha no SRT.

        Returns:
            Dicionário com a resposta da API.
        """
        if not self.api_key:
            raise ValueError("API Key não configurada. Defina TRANSCRIBE_API_KEY no .env ou passe no construtor.")

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "media_url": media_url,
            "task": task,
            "include_text": include_text,
            "include_srt": include_srt,
            "include_segments": include_segments,
            "word_timestamps": word_timestamps,
            "response_type": response_type
        }

        if webhook_url:
            payload["webhook_url"] = webhook_url
        if job_id:
            payload["id"] = job_id
        if max_words_per_line:
            payload["max_words_per_line"] = max_words_per_line

        try:
            print(f"DEBUG: Chamando API em {self.api_url}")
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=300)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Erro ao chamar API de transcrição: {e}")
            if hasattr(e.response, 'text'):
                print(f"Resposta do servidor: {e.response.text}")
            raise

def transcribe_media(media_url: str, **kwargs) -> Dict[str, Any]:
    """Função helper para facilitar o uso rápido."""
    client = Transcriber()
    return client.transcribe(media_url, **kwargs)

if __name__ == "__main__":
    # Exemplo de uso
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python transcribe.py <media_url>")
        sys.exit(1)
        
    url = sys.argv[1]
    print(f"Transcrevendo: {url}...")
    
    try:
        result = transcribe_media(
            url, 
            include_srt=True, 
            include_segments=True
        )
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Falha na transcrição: {e}")
