GeneratedWorld_Wilds_MapScripts::
	.byte 0

	.ifdef PORTABLE
GeneratedWorld_Wilds_EventScript_Guide::
	msgbox gGeneratedWildsGuideText, MSGBOX_NPC
	end
GeneratedWorld_Wilds_EventScript_Cast2::
	msgbox gGeneratedWildsCastText2, MSGBOX_NPC
	end
GeneratedWorld_Wilds_EventScript_Cast3::
	msgbox gGeneratedWildsCastText3, MSGBOX_NPC
	end
GeneratedWorld_Wilds_EventScript_Graph::
	special GeneratedMap_RunEvent
	msgbox gGeneratedEventText, MSGBOX_NPC
	end
	.endif
