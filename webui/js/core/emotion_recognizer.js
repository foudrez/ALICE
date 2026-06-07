import { globalEventBus } from './event_bus.js';

export class EmotionRecognizer {
    constructor() {
        this.currentEmotion = 'neutral';
        this.currentWeights = { neutral: 1.0 };
        this.currentAction = 'none';
    }

    analyze(text) {
        let emotion = 'neutral';
        let action = 'none';
        let weights = {};
        
        const lowerText = text.toLowerCase();

        // 1. Check for explicit LLM Action Tags (e.g., [wave], [nod], [shake])
        if (lowerText.includes('[wave]')) action = 'wave';
        if (lowerText.includes('[nod]')) action = 'nod';
        if (lowerText.includes('[shake]')) action = 'shake_head';
        
        // 2. Parse explicit LLM Emotion Tags (e.g., [happy:50], [happy:40, surprised:20], [joy])
        const tagRegex = /\[(.*?)\]/g;
        let match;
        let foundEmotionTag = false;

        while ((match = tagRegex.exec(lowerText)) !== null) {
            const tagContent = match[1].trim();
            
            // If it contains a colon, it's a percent-based emotion tag (or list of them)
            if (tagContent.includes(':')) {
                foundEmotionTag = true;
                const parts = tagContent.split(',');
                parts.forEach(part => {
                    const subParts = part.split(':');
                    if (subParts.length === 2) {
                        const rawName = subParts[0].trim();
                        const rawVal = parseFloat(subParts[1].trim());
                        
                        let mappedName = null;
                        if (['happy', 'joy'].includes(rawName)) mappedName = 'happy';
                        else if (['sad', 'sorrow'].includes(rawName)) mappedName = 'sad';
                        else if (['angry', 'mad'].includes(rawName)) mappedName = 'angry';
                        else if (['surprised', 'panic'].includes(rawName)) mappedName = 'surprised';
                        else if (['relaxed', 'chill'].includes(rawName)) mappedName = 'relaxed';
                        else if (rawName === 'neutral') mappedName = 'neutral';
                        
                        if (mappedName && !isNaN(rawVal)) {
                            let val = rawVal;
                            if (val > 1.0) {
                                val = val / 100.0;
                            }
                            val = Math.max(0, Math.min(1.0, val));
                            weights[mappedName] = (weights[mappedName] || 0) + val;
                        }
                    }
                });
            } else {
                // Check if it matches simple emotion tags without weights, e.g. [happy]
                let mappedName = null;
                if (['happy', 'joy'].includes(tagContent)) mappedName = 'happy';
                else if (['sad', 'sorrow'].includes(tagContent)) mappedName = 'sad';
                else if (['angry', 'mad'].includes(tagContent)) mappedName = 'angry';
                else if (['surprised', 'panic'].includes(tagContent)) mappedName = 'surprised';
                else if (['relaxed', 'chill'].includes(tagContent)) mappedName = 'relaxed';
                else if (tagContent === 'neutral') mappedName = 'neutral';

                if (mappedName) {
                    foundEmotionTag = true;
                    weights[mappedName] = 1.0;
                }
            }
        }

        // 3. Fallback: If no explicit tag, guess based on keywords
        if (!foundEmotionTag) {
            if (lowerText.match(/(love|amazing|great|yay|haha)/)) emotion = 'happy';
            else if (lowerText.match(/(hate|stop|annoying|bad)/)) emotion = 'angry';
            else if (lowerText.match(/(sorry|apologize|miss you)/)) emotion = 'sad';
            else if (lowerText.match(/(wow|omg|really|unbelievable)/)) emotion = 'surprised';
            
            if (emotion !== 'neutral') {
                weights[emotion] = 0.5; // Default keyword guess to 50%
            } else {
                weights['neutral'] = 1.0;
            }
        }

        // Determine primary emotion name (one with the highest weight)
        let primaryEmotion = 'neutral';
        let maxWeight = 0;
        for (const [emo, weight] of Object.entries(weights)) {
            if (emo !== 'neutral' && weight > maxWeight) {
                maxWeight = weight;
                primaryEmotion = emo;
            }
        }
        if (maxWeight === 0 && weights['neutral'] === undefined) {
            weights['neutral'] = 1.0;
        }

        // Prepare structured emotion payload
        const emotionData = {
            primary: primaryEmotion,
            weights: weights
        };

        // Only emit if the weights have changed
        const weightsChanged = JSON.stringify(this.currentWeights) !== JSON.stringify(weights);
        if (weightsChanged) {
            this.currentWeights = weights;
            this.currentEmotion = primaryEmotion;
            globalEventBus.emit('emotion_triggered', emotionData);
        }

        if (action !== 'none') {
            this.currentAction = action;
            globalEventBus.emit('action_triggered', this.currentAction);
        }
    }
}