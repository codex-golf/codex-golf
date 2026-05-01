package main

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/code-golf/code-golf/config"
	"github.com/code-golf/code-golf/hole"
)

func usage() {
	fmt.Fprintf(os.Stderr, "usage: upstream-play <hole> <lang> <answer-file>\n")
	os.Exit(64)
}

func snippet(s string) string {
	const max = 4000
	if len(s) <= max {
		return s
	}
	return s[:max] + "\n... truncated ..."
}

func main() {
	if len(os.Args) != 4 {
		usage()
	}

	holeID, langID, file := os.Args[1], os.Args[2], os.Args[3]
	h := config.AllHoleByID[holeID]
	if h == nil {
		fmt.Fprintf(os.Stderr, "::error::unknown hole: %s\n", holeID)
		os.Exit(64)
	}
	l := config.AllLangByID[langID]
	if l == nil {
		fmt.Fprintf(os.Stderr, "::error::unknown lang: %s\n", langID)
		os.Exit(64)
	}

	codeBytes, err := os.ReadFile(file)
	if err != nil {
		fmt.Fprintf(os.Stderr, "::error::read %s: %v\n", file, err)
		os.Exit(66)
	}
	// Keep parity with upstream POST /solution. We call hole.Play() directly,
	// so the HTTP handler's code-size gate would otherwise be bypassed.
	if len(codeBytes) >= 128*1024 {
		fmt.Fprintln(os.Stderr, "::error::solution too large: code must be <128KiB")
		os.Exit(65)
	}
	code := string(codeBytes)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	runs, err := hole.Play(ctx, h, l, code)
	if err != nil {
		fmt.Fprintf(os.Stderr, "::error::official runner error: %v\n", err)
		os.Exit(70)
	}

	allPass := len(runs) > 0
	for i, run := range runs {
		if run.Pass {
			continue
		}
		allPass = false
		fmt.Printf("::error::run %d failed\n", i+1)
		if len(run.Args) > 0 {
			fmt.Printf("args: %s\n", strings.Join(run.Args, " "))
		}
		fmt.Printf("exit_code: %d timeout: %t\n", run.ExitCode, run.Timeout)
		if run.Stderr != "" {
			fmt.Printf("--- stderr ---\n%s\n", snippet(run.Stderr))
		}
		fmt.Printf("--- expected ---\n%s\n", snippet(run.Answer))
		fmt.Printf("--- actual ---\n%s\n", snippet(run.Stdout))
	}

	if !allPass {
		os.Exit(1)
	}

	fmt.Printf("PASS %d\n", len(codeBytes))
}
