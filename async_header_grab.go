package main

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

type Result struct {
	Host    string
	Port    int
	Headers http.Header
}

// func explodeCIDRs(cidr string) ([]string, error) {
// 	ipnet, err := net.ParseCIDR(cidr)
// 	if err != nil {
// 		return nil, err
// 	}
// 	var ips []string
// 	for ip := ipnet.IP.Mask(ipnet.Mask); ipnet.Contains(ip); inc(ip) {
// 		ips = append(ips, ip.String())
// 	}
// 	return ips, nil
// }

func explodeCIDRs(cidr string) ([]string, error) {
	ip, ipnet, err := net.ParseCIDR(cidr)
	if err != nil {
		return nil, err
	}
	var ips []string
	for ip := ip.Mask(ipnet.Mask); ipnet.Contains(ip); inc(ip) {
		ips = append(ips, ip.String())
	}
	return ips, nil
}

func inc(ip net.IP) {
	for j := len(ip) - 1; j >= 0; j-- {
		ip[j]++
		if ip[j] > 0 {
			break
		}
	}
}

func getHeader(ctx context.Context, resultsChan chan<- *Result, host string, port int, timeout time.Duration) {
	client := &http.Client{
		Timeout: timeout,
		Transport: &http.Transport{
			DisableKeepAlives:   true,
			MaxIdleConnsPerHost: 0,
			TLSClientConfig:     &tls.Config{InsecureSkipVerify: true},
		},
	}

	headers := http.Header{
		"User-Agent": []string{"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"},
	}

	request, err := http.NewRequestWithContext(ctx, http.MethodHead, fmt.Sprintf("https://%s:%d", host, port), nil)
	if err != nil {
		resultsChan <- &Result{Host: host, Port: port, Headers: nil}
		return
	}
	request.Header = headers

	response, err := client.Do(request)
	if err != nil {
		request.URL.Scheme = "http"
		response, err = client.Do(request)
		if err != nil {
			resultsChan <- &Result{Host: host, Port: port, Headers: nil}
			return
		}
	}

	resultsChan <- &Result{Host: host, Port: port, Headers: response.Header}
}

func worker(ctx context.Context, targets <-chan string, ports []int, timeout time.Duration, resultsChan chan<- *Result) {
	for {
		select {
		case host, ok := <-targets:
			if !ok {
				return
			}
			for _, port := range ports {
				getHeader(ctx, resultsChan, host, port, timeout)
			}
		case <-ctx.Done():
			return
		}
	}
}

func main() {
	host := flag.String("host", "", "A single host to query")
	infile := flag.String("infile", "/tmp/scan_targets.txt", "A file containing a newline-separated list of hosts")
	ports := flag.String("ports", "", "The port(s) to which we want to connect")
	outfile := flag.String("outfile", "/tmp/scan_results.json", "The file to which we want to dump our results")
	timeout := flag.Int("timeout", 3, "Timeout for the HTTP connection")
	flag.Parse()

	startTime := time.Now()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	var targets []string
	if *host != "" {
		targets = []string{*host}
	} else {
		targetsData, err := ioutil.ReadFile(*infile)
		if err != nil {
			fmt.Printf("Error reading infile: %s\n", err)
			os.Exit(1)
		}
		targets = strings.Split(strings.TrimSpace(string(targetsData)), "\n")
	}

	portsList := strings.Split(*ports, ",")
	portsInt := make([]int, len(portsList))
	for i, port := range portsList {
		p, err := strconv.Atoi(strings.TrimSpace(port))
		if err != nil {
			fmt.Printf("Error parsing port: %s\n", err)
			os.Exit(1)
		}
		portsInt[i] = p
	}

	timeoutDuration := time.Duration(*timeout) * time.Second

	targetsChan := make(chan string, len(targets))
	resultsChan := make(chan *Result, len(targets)*len(portsInt))

	for i := 0; i < 10; i++ {
		go worker(ctx, targetsChan, portsInt, timeoutDuration, resultsChan)
	}

	for _, target := range targets {
		if _, _, err := net.ParseCIDR(target); err == nil {
			ips, err := explodeCIDRs(target)
			if err != nil {
				fmt.Printf("Error exploding CIDRs: %s\n", err)
				continue
			}
			for _, ip := range ips {
				targetsChan <- ip
			}
		} else {
			targetsChan <- target
		}
	}
	close(targetsChan)

	var results []*Result
	for i := 0; i < len(targets)*len(portsInt); i++ {
		res := <-resultsChan
		results = append(results, res)
		fmt.Println(*res)
	}
	close(resultsChan)

	output, err := json.MarshalIndent(results, "", "  ")
	if err != nil {
		fmt.Printf("Error marshalling results: %s\n", err)
		os.Exit(1)
	}

	err = ioutil.WriteFile(*outfile, output, 0644)
	if err != nil {
		fmt.Printf("Error writing output file: %s\n", err)
		os.Exit(1)
	}

	endTime := time.Now()
	duration := endTime.Sub(startTime)

	fmt.Printf("Total time taken: %s\n", duration)
}
