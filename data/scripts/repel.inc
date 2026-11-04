EventScript_RepelWoreOff::
	.ifdef PORTABLE
	@ Repel-only whole interaction adapted from RHH pokeemerald-expansion
	@ c460a8661dfa0598ae25d42a968c690ecbf489c6 data/scripts/repel.inc.
	@ See upstream README.md and CREDITS.md for contributor credits.
	lockall
	callnative RepeatRepel_Begin
RepeatRepel_AfterBegin::
	compare VAR_RESULT, 0
	goto_if_eq RepeatRepel_NoStock
	compare VAR_RESULT, 1
	goto_if_eq RepeatRepel_Single
	message RepeatRepel_Text_Choose
	waitmessage
	callnative RepeatRepel_DrawMenu
RepeatRepel_AfterDraw::
	compare VAR_RESULT, FALSE
	goto_if_eq RepeatRepel_Done
	waitstate
	@ B and the explicit Cancel index both fail the guarded commit.
	goto RepeatRepel_Use

RepeatRepel_Single:
	bufferitemname STR_VAR_2, VAR_0x8004
	msgbox RepeatRepel_Text_AskUse, MSGBOX_YESNO
	compare VAR_RESULT, YES
	goto_if_ne RepeatRepel_Done
	setvar VAR_RESULT, 0
RepeatRepel_Use:
	callnative RepeatRepel_Commit
RepeatRepel_AfterCommit::
	compare VAR_RESULT, TRUE
	goto_if_ne RepeatRepel_Done
	playse SE_REPEL
	waitse
	bufferitemname STR_VAR_2, VAR_0x8004
	msgbox RepeatRepel_Text_Used, MSGBOX_SIGN
	goto RepeatRepel_Done

RepeatRepel_NoStock:
	msgbox Text_RepelWoreOff, MSGBOX_SIGN
RepeatRepel_Done:
	callnative RepeatRepel_End
	closemessage
	releaseall
	end
	.else
	msgbox Text_RepelWoreOff, MSGBOX_SIGN
	end
	.endif

Text_RepelWoreOff:
	.string "REPEL's effect wore off…$"

	.ifdef PORTABLE
RepeatRepel_Text_Choose:
	.string "REPEL's effect wore off!\n"
	.string "Use another?$"

RepeatRepel_Text_AskUse:
	.string "REPEL's effect wore off…\n"
	.string "Use a {STR_VAR_2}?$"

RepeatRepel_Text_Used:
	.string "{PLAYER} used the\n"
	.string "{STR_VAR_2}.$"
	.endif
