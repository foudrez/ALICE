export class EmotionRecognizer {
    constructor() {
        // Fast keyword matching dictionary
        this.dictionary = {
            happy: ['joy', 'happy', 'great', 'love', 'amazing', 'haha', 'yay', 'glad', 'wonderful', 'smile'],
            sad: ['sad', 'sorry', 'apologize', 'bad', 'terrible', 'miss', 'unfortunate', 'hurt'],
            angry: ['angry', 'mad', 'hate', 'stop', 'annoying', 'frustrating', 'furious', 'never'],
            surprised: ['wow', 'omg', 'really', 'shocking', 'whoa', 'incredible', 'unbelievable']
        };
        this.currentEmotion = 'neutral';
    }

    analyze(text) {
        const lowerText = text.toLowerCase();
        
        // Scan the sentence for emotional triggers
        for (const [emotion, words] of Object.entries(this.dictionary)) {
            if (words.some(word => lowerText.includes(word))) {
                this.currentEmotion = emotion;
                return emotion;
            }
        }
        
        // Default back to neutral if no strong emotion is detected
        this.currentEmotion = 'neutral';
        return 'neutral';
    }
}