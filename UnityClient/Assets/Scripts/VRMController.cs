using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using VRM; // Requires UniVRM package

public class VRMController : MonoBehaviour
{
    private VRMBlendShapeProxy blendShapeProxy;
    private Animator animator;

    private Dictionary<string, BlendShapeKey> emotionKeys = new Dictionary<string, BlendShapeKey>()
    {
        { "joy", BlendShapeKey.CreateFromPreset(BlendShapePreset.Joy) },
        { "angry", BlendShapeKey.CreateFromPreset(BlendShapePreset.Angry) },
        { "sad", BlendShapeKey.CreateFromPreset(BlendShapePreset.Sorrow) },
        { "surprised", BlendShapeKey.CreateFromPreset(BlendShapePreset.Surprised) },
        { "relaxed", BlendShapeKey.CreateFromPreset(BlendShapePreset.Fun) },
        { "neutral", BlendShapeKey.CreateFromPreset(BlendShapePreset.Neutral) }
    };

    void Start()
    {
        blendShapeProxy = GetComponent<VRMBlendShapeProxy>();
        animator = GetComponent<Animator>();
        
        if (blendShapeProxy == null)
        {
            Debug.LogWarning("VRMBlendShapeProxy not found on this GameObject. Ensure UniVRM is installed and the script is attached to the VRM root.");
        }
    }

    public void SetEmotion(string emotionString)
    {
        if (blendShapeProxy == null) return;

        string cleanEmotion = emotionString.ToLower().Trim();
        
        // Reset all preset emotions
        foreach (var key in emotionKeys.Values)
        {
            blendShapeProxy.ImmediatelySetValue(key, 0f);
        }

        // Apply new emotion
        if (emotionKeys.ContainsKey(cleanEmotion))
        {
            blendShapeProxy.ImmediatelySetValue(emotionKeys[cleanEmotion], 1.0f);
        }
        else
        {
            // Fallback to neutral
            blendShapeProxy.ImmediatelySetValue(emotionKeys["neutral"], 1.0f);
        }

        // Optional: Trigger an animation state if you set up an Animator Controller
        if (animator != null && animator.runtimeAnimatorController != null)
        {
            // Assuming your animator has a trigger parameter named after the emotion
            // animator.SetTrigger(cleanEmotion);
        }
    }
}
