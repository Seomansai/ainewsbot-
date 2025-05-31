# Система контроля расходов для AI News Bot
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

class CostTracker:
    """Отслеживание расходов на AI модели"""
    
    def __init__(self, max_monthly_budget: float = 5.0, storage_path: str = "cost_data.json"):
        self.max_monthly_budget = max_monthly_budget
        self.storage_path = storage_path
        self.costs = self._load_costs()
        
    def _load_costs(self) -> Dict:
        """Загрузка данных о расходах"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Ошибка загрузки данных о расходах: {e}")
        
        return {
            "monthly_costs": {},
            "daily_costs": {},
            "model_usage": {}
        }
    
    def _save_costs(self):
        """Сохранение данных о расходах"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.costs, f, indent=2)
        except Exception as e:
            logging.error(f"Ошибка сохранения данных о расходах: {e}")
    
    def get_current_month_key(self) -> str:
        """Получение ключа текущего месяца"""
        return datetime.now().strftime("%Y-%m")
    
    def get_current_day_key(self) -> str:
        """Получение ключа текущего дня"""
        return datetime.now().strftime("%Y-%m-%d")
    
    def can_afford_request(self, estimated_cost: float) -> bool:
        """Проверка, можем ли позволить себе запрос"""
        month_key = self.get_current_month_key()
        current_monthly_cost = self.costs["monthly_costs"].get(month_key, 0.0)
        
        return (current_monthly_cost + estimated_cost) <= self.max_monthly_budget
    
    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Оценка стоимости запроса"""
        # Цены за 1M токенов (актуальные на декабрь 2024)
        model_prices = {
            "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
            "openai/gpt-4o": {"input": 2.5, "output": 10.0},
            "openai/gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
            "meta-llama/llama-3.1-8b-instruct:free": {"input": 0.0, "output": 0.0},
            "microsoft/wizardlm-2-8x22b:free": {"input": 0.0, "output": 0.0},
        }
        
        if model not in model_prices:
            logging.warning(f"Неизвестная модель {model}, используем среднюю цену")
            return (input_tokens * 1.0 + output_tokens * 3.0) / 1_000_000
        
        prices = model_prices[model]
        input_cost = (input_tokens * prices["input"]) / 1_000_000
        output_cost = (output_tokens * prices["output"]) / 1_000_000
        
        return input_cost + output_cost
    
    def record_usage(self, model: str, input_tokens: int, output_tokens: int, actual_cost: Optional[float] = None):
        """Запись использования модели"""
        if actual_cost is None:
            actual_cost = self.estimate_cost(model, input_tokens, output_tokens)
        
        month_key = self.get_current_month_key()
        day_key = self.get_current_day_key()
        
        # Обновляем месячные расходы
        if month_key not in self.costs["monthly_costs"]:
            self.costs["monthly_costs"][month_key] = 0.0
        self.costs["monthly_costs"][month_key] += actual_cost
        
        # Обновляем дневные расходы
        if day_key not in self.costs["daily_costs"]:
            self.costs["daily_costs"][day_key] = 0.0
        self.costs["daily_costs"][day_key] += actual_cost
        
        # Обновляем статистику использования модели
        if model not in self.costs["model_usage"]:
            self.costs["model_usage"][model] = {
                "total_cost": 0.0,
                "total_requests": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0
            }
        
        model_stats = self.costs["model_usage"][model]
        model_stats["total_cost"] += actual_cost
        model_stats["total_requests"] += 1
        model_stats["total_input_tokens"] += input_tokens
        model_stats["total_output_tokens"] += output_tokens
        
        self._save_costs()
        
        # Логирование
        logging.info(f"💰 Использование {model}: ${actual_cost:.4f} (месяц: ${self.costs['monthly_costs'][month_key]:.2f})")
    
    def get_monthly_spending(self, month: Optional[str] = None) -> float:
        """Получение месячных расходов"""
        if month is None:
            month = self.get_current_month_key()
        return self.costs["monthly_costs"].get(month, 0.0)
    
    def get_remaining_budget(self) -> float:
        """Получение остатка бюджета"""
        current_spending = self.get_monthly_spending()
        return max(0.0, self.max_monthly_budget - current_spending)
    
    def suggest_model(self, required_quality: str = "medium") -> str:
        """Предложение модели в зависимости от бюджета и требований"""
        remaining = self.get_remaining_budget()
        
        if remaining <= 0:
            return "meta-llama/llama-3.1-8b-instruct:free"
        
        if required_quality == "high" and remaining > 1.0:
            return "anthropic/claude-3.5-sonnet"
        elif required_quality == "medium" and remaining > 0.1:
            return "openai/gpt-3.5-turbo"
        else:
            return "meta-llama/llama-3.1-8b-instruct:free"
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """Очистка старых данных"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        
        # Очистка дневных данных
        old_days = [day for day in self.costs["daily_costs"].keys() if day < cutoff_str]
        for day in old_days:
            del self.costs["daily_costs"][day]
        
        # Очистка месячных данных (оставляем последние 12 месяцев)
        cutoff_month = cutoff_date.strftime("%Y-%m")
        old_months = [month for month in self.costs["monthly_costs"].keys() if month < cutoff_month]
        for month in old_months[:-12]:  # Оставляем последние 12 месяцев
            del self.costs["monthly_costs"][month]
        
        self._save_costs()

# Пример использования в боте
class SmartTranslator:
    """Переводчик с умным выбором модели"""
    
    def __init__(self, openrouter_api_key: str, max_monthly_budget: float = 5.0):
        self.client = OpenAI(api_key=openrouter_api_key, base_url="https://openrouter.ai/api/v1")
        self.cost_tracker = CostTracker(max_monthly_budget)
    
    async def translate_news(self, text: str, quality: str = "medium") -> str:
        """Перевод с контролем расходов"""
        # Оценка количества токенов
        estimated_input_tokens = len(text) // 4  # Примерная оценка
        estimated_output_tokens = estimated_input_tokens // 2
        
        # Выбор модели
        model = self.cost_tracker.suggest_model(quality)
        
        # Проверка бюджета
        estimated_cost = self.cost_tracker.estimate_cost(
            model, estimated_input_tokens, estimated_output_tokens
        )
        
        if not self.cost_tracker.can_afford_request(estimated_cost):
            logging.warning("🚫 Превышен месячный бюджет, используем бесплатную модель")
            model = "meta-llama/llama-3.1-8b-instruct:free"
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Создай краткое резюме на русском языке."},
                    {"role": "user", "content": text}
                ],
                temperature=0.3
            )
            
            # Запись использования
            usage = response.usage
            self.cost_tracker.record_usage(
                model, 
                usage.prompt_tokens, 
                usage.completion_tokens
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logging.error(f"Ошибка перевода: {e}")
            raise 