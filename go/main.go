package main

import (
	"log"

	"github.com/lxn/walk"
)

func main() {
	if err := InitDB(); err != nil {
		log.Fatal("DB init failed: ", err)
	}
	a := &App{}
	if err := a.run(); err != nil {
		walk.MsgBox(nil, "LedgerTimer", "Fatal error: "+err.Error(), walk.MsgBoxIconError)
		log.Fatal(err)
	}
}
