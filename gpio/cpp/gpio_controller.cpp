// Copyright (c) 2025 by T3 Foundation. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//     https://docs.t3gemstone.org/en/license
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// SPDX-License-Identifier: Apache-2.0

#include "gpio_controller.h"
#include <iostream>
#include <threads.h>
#include <unistd.h>

GpioController::GpioController() {}

GpioController::~GpioController()
{
    if (m_line_gpio27)
    {
        gpiod_line_release(m_line_gpio27);
        m_line_gpio27 = nullptr;
    }
    if (m_line_led_red)
    {
        gpiod_line_release(m_line_led_red);
        m_line_led_red = nullptr;
    }
    if (m_line_led_green)
    {
        gpiod_line_release(m_line_led_green);
        m_line_led_green = nullptr;
    }
    if (m_line_gpio22)
    {
        gpiod_line_release(m_line_gpio22);
        m_line_gpio22 = nullptr;
    }

    if (m_chip1)
    {
        gpiod_chip_close(m_chip1);
        m_chip1 = nullptr;
    }
}

void GpioController::delay_ms(int ms)
{
    struct timespec request = {ms / 1000, (ms % 1000) * 1'000'000};
    struct timespec remaining;

    while (thrd_sleep(&request, &remaining) == -1 && errno == EINTR)
    {
        request = remaining; // Sleep again with remaining time if interrupted
    }
}

int GpioController::initialize()
{
    m_chip1 = gpiod_chip_open_by_name("gpiochip1");
    if (!m_chip1)
    {
        std::cerr << "Failed to open gpiochip1" << std::endl;
        return 1;
    }

    m_line_gpio27 = gpiod_chip_get_line(m_chip1, 33);
    m_line_led_red = gpiod_chip_get_line(m_chip1, 11);
    m_line_led_green = gpiod_chip_get_line(m_chip1, 12);
    m_line_gpio22 = gpiod_chip_get_line(m_chip1, 41);

    if (!m_line_gpio27 || !m_line_led_red || !m_line_led_green || !m_line_gpio22)
    {
        std::cerr << "Failed to get GPIO lines" << std::endl;
        return 1;
    }

    if (configure_outputs() || configure_inputs())
    {
        return 1;
    }

    // Read initial state of input
    m_prev_input_state = gpiod_line_get_value(m_line_gpio22);
    if (m_prev_input_state < 0)
    {
        std::cerr << "Failed to read initial input state" << std::endl;
        return 1;
    }

    print_configuration();

    return 0;
}

int GpioController::configure_outputs()
{
    // Configure gpiochip1-33 as active-high output with value 0
    int ret = gpiod_line_request_output(m_line_gpio27, "gpio_example", 0);
    if (ret < 0)
    {
        std::cerr << "Failed to configure line1-33 as output" << std::endl;
        return 1;
    }

    // Configure gpiochip1-11 as active-low output with value 0
    ret = gpiod_line_request_output_flags(m_line_led_red, "gpio_example", GPIOD_LINE_REQUEST_FLAG_ACTIVE_LOW, 0);
    if (ret < 0)
    {
        std::cerr << "Failed to configure line1-11 as active-low output" << std::endl;
        return 1;
    }

    // Configure gpiochip1-12 as active-high output with value 0
    ret = gpiod_line_request_output(m_line_led_green, "gpio_example", 0);
    if (ret < 0)
    {
        std::cerr << "Failed to configure line1-12 as output" << std::endl;
        return 1;
    }

    return 0;
}

int GpioController::configure_inputs()
{
    // Configure gpiochip1-41 as pull-up input
    int ret = gpiod_line_request_input_flags(m_line_gpio22, "gpio_example", GPIOD_LINE_REQUEST_FLAG_BIAS_PULL_UP);
    if (ret < 0)
    {
        std::cerr << "Failed to configure line1-41 as input" << std::endl;
        return 1;
    }

    return 0;
}

void GpioController::print_configuration()
{
    std::cout << "GPIO configuration complete:" << std::endl;
    std::cout << "- gpiochip1-33 (GPIO27)   : active-high output, value=0" << std::endl;
    std::cout << "- gpiochip1-11 (RED LED)  : active-low output , value=0" << std::endl;
    std::cout << "- gpiochip1-12 (GREEN LED): active-high output, value=0" << std::endl;
    std::cout << "- gpiochip1-41 (GPIO22)   : pull-up input" << std::endl;
    std::cout << std::endl;
    std::cout << "Waiting for input transitions on GPIO22..." << std::endl;
    std::cout << "Press Ctrl+C to exit" << std::endl << std::endl;
}

void GpioController::run()
{
    m_is_running = true;
    while (m_is_running)
    {
        m_current_input_state = gpiod_line_get_value(m_line_gpio22);
        if (m_current_input_state < 0)
        {
            std::cerr << "Failed to read input state" << std::endl;
            break;
        }

        if (m_prev_input_state == 1 && m_current_input_state == 0)
        {
            int ret = gpiod_line_set_value(m_line_led_red, 1);
            if (ret < 0)
            {
                std::cerr << "Failed to set LED_RED" << std::endl;
                break;
            }
            ret = gpiod_line_set_value(m_line_led_green, 0);
            if (ret < 0)
            {
                std::cerr << "Failed to set LED_GREEN" << std::endl;
                break;
            }
            std::cout << "-> Set LED_RED=HIGH, LED_GREEN=LOW" << std::endl;
        }
        if (m_prev_input_state == 0 && m_current_input_state == 1)
        {
            int ret = gpiod_line_set_value(m_line_led_red, 0);
            if (ret < 0)
            {
                std::cerr << "Failed to set LED_RED" << std::endl;
                break;
            }
            ret = gpiod_line_set_value(m_line_led_green, 1);
            if (ret < 0)
            {
                std::cerr << "Failed to set LED_GREEN" << std::endl;
                break;
            }
            std::cout << "-> Set LED_RED=LOW, LED_GREEN=HIGH" << std::endl;
        }

        m_prev_input_state = m_current_input_state;

        // Small delay to avoid excessive CPU usage
        delay_ms(10);
    }
}

void GpioController::stop()
{
    m_is_running = false;
}
